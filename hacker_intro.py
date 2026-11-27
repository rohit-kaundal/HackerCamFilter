#!/usr/bin/env python3
"""Hacker-style intro for video calls (Zoom, Teams, Meet, ...).

Renders a "matrix rain -> terminal breach -> ACCESS GRANTED -> name reveal"
animation into a virtual camera, then hands over to your real webcam.
In the call app, pick "OBS Virtual Camera" as your camera.

Hotkeys (global, work while the call app is focused):
    Ctrl+Alt+H  replay the intro
    Ctrl+Alt+G  toggle the live hacker filter on your webcam
    Ctrl+Alt+M  toggle the matrix-rain background (needs mediapipe)
    Ctrl+Alt+B  run a biometric face scan (needs mediapipe)
    Ctrl+Alt+T  toggle the global-trace world map background (needs mediapipe)
    Ctrl+Alt+O  toggle hologram mode (needs mediapipe)
    Ctrl+Alt+E  entrance: assemble into view out of particles (needs mediapipe)
    Ctrl+Alt+A  toggle the "session suspended" away screen
    Ctrl+Alt+Q  quit
"""
import argparse
import os
import queue
import random
import sys
import threading
import time
import urllib.request

import cv2
import numpy as np

GREEN = (70, 255, 70)          # BGR
DIM_GREEN = (40, 150, 40)
AMBER = (0, 190, 255)
HEAD_COLOR = (220, 255, 220)
GLYPHS = "0123456789ABCDEF@#$%&*+=<>/\\|{}[]?!"

# Base phase durations in seconds (multiplied by --duration-scale).
PHASES = [
    ("rain", 2.5),
    ("terminal", 3.2),
    ("granted", 1.3),
    ("name", 2.4),
    ("transition", 0.9),
]


# ---------------------------------------------------------------- effects ---

def glitch(frame, intensity, rng):
    """Horizontal band displacement plus RGB channel split."""
    if intensity <= 0.01:
        return frame
    h, w = frame.shape[:2]
    out = frame.copy()
    for _ in range(int(3 + 12 * intensity)):
        y0 = rng.randrange(0, h)
        y1 = min(h, y0 + rng.randrange(3, max(4, int(45 * intensity))))
        dx = rng.randint(-int(80 * intensity) - 1, int(80 * intensity) + 1)
        out[y0:y1] = np.roll(out[y0:y1], dx, axis=1)
    s = int(10 * intensity)
    if s:
        out[:, :, 2] = np.roll(out[:, :, 2], s, axis=1)
        out[:, :, 0] = np.roll(out[:, :, 0], -s, axis=1)
    return out


def make_scanline_mask(w, h):
    mask = np.full((h, w, 3), 255, np.uint8)
    mask[::3] = 150
    return mask


def scanlines(frame, mask):
    return cv2.multiply(frame, mask, scale=1 / 255)


def crossfade(a, b, alpha):
    return cv2.addWeighted(a, 1 - alpha, b, alpha, 0)


def fit_scale(text, font, scale, thickness, max_width):
    tw = cv2.getTextSize(text, font, scale, thickness)[0][0]
    return scale * min(1.0, max_width / max(tw, 1))


def put_centered(frame, text, cy, font, scale, thickness, color, glow=False):
    """Draw text centred horizontally at baseline-ish y = cy; optional glow."""
    h, w = frame.shape[:2]
    scale = fit_scale(text, font, scale, thickness, w * 0.9)
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    org = ((w - tw) // 2, cy + th // 2)
    if glow:
        layer = np.zeros_like(frame)
        cv2.putText(layer, text, org, font, scale, color, thickness + 4, cv2.LINE_AA)
        frame[:] = cv2.add(frame, cv2.GaussianBlur(layer, (0, 0), 10))
    cv2.putText(frame, text, org, font, scale, color, thickness, cv2.LINE_AA)
    return frame


def resize_cover(img, w, h):
    """Resize keeping aspect ratio, cropping the overflow (like CSS cover)."""
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    img = cv2.resize(img, (int(iw * s + 0.5), int(ih * s + 0.5)))
    ih, iw = img.shape[:2]
    x0, y0 = (iw - w) // 2, (ih - h) // 2
    return img[y0:y0 + h, x0:x0 + w]


# ------------------------------------------------------------ matrix rain ---

class Rain:
    def __init__(self, w, h, rng, cell):
        self.w, self.h, self.cell, self.rng = w, h, cell, rng
        self.cols = w // cell
        self.y = [rng.uniform(-h, 0) for _ in range(self.cols)]
        self.speed = [rng.uniform(250, 700) * h / 720 for _ in range(self.cols)]
        self.trail = np.zeros((h, w, 3), np.uint8)
        self.font_scale = cell / 16

    def warm(self, seconds=2.5, fps=30):
        """Pre-run the rain so it starts out filling the screen."""
        for _ in range(int(seconds * fps)):
            self.step(1 / fps)
        return self

    def step(self, dt):
        """Advance the rain by dt seconds and return the rendered frame."""
        self.trail = cv2.convertScaleAbs(self.trail, alpha=0.88)
        heads = []
        for i in range(self.cols):
            self.y[i] += self.speed[i] * dt
            if self.y[i] > self.h + self.rng.uniform(0, self.h * 0.6):
                self.y[i] = self.rng.uniform(-self.h * 0.4, 0)
                self.speed[i] = self.rng.uniform(250, 700) * self.h / 720
            row = int(self.y[i] // self.cell) * self.cell
            if 0 <= row < self.h + self.cell:
                org = (i * self.cell + 2, row)
                ch = self.rng.choice(GLYPHS)
                cv2.putText(self.trail, ch, org, cv2.FONT_HERSHEY_PLAIN,
                            self.font_scale, GREEN, 1, cv2.LINE_AA)
                heads.append((ch, org))
        out = self.trail.copy()
        for ch, org in heads:
            cv2.putText(out, ch, org, cv2.FONT_HERSHEY_PLAIN,
                        self.font_scale, HEAD_COLOR, 1, cv2.LINE_AA)
        return out


# ------------------------------------------------------------------ intro ---

class Intro:
    def __init__(self, w, h, name, title, duration_scale=1.0, seed=None):
        self.w, self.h = w, h
        self.name, self.title = name, title
        self.rng = random.Random(seed)
        self.k = h / 720  # size factor relative to 720p
        self.rain = Rain(w, h, self.rng, cell=max(10, int(16 * self.k)))
        self.mask = make_scanline_mask(w, h)
        self.phases = []
        start = 0.0
        for pname, dur in PHASES:
            dur *= duration_scale
            self.phases.append((pname, start, start + dur))
            start += dur
        self.total = start
        self.last_t = 0.0
        self.last_intro_frame = None
        self.lines = self._breach_lines()

    def _breach_lines(self):
        r = self.rng
        ip = ".".join(str(r.randint(10, 254)) for _ in range(4))
        return [
            "> initializing secure uplink ...",
            f"> target acquired: {ip}:{r.choice([22, 443, 8443, 31337])}",
            "> bypassing firewall ...",
            "%PROGRESS%",
            f"> injecting payload 0x{r.getrandbits(32):08X}",
            "> " + " ".join(f"{r.getrandbits(8):02x}" for _ in range(16)),
            "> decrypting credentials ... OK",
            "> handshake complete. session established.",
        ]

    def _phase(self, t):
        for pname, a, b in self.phases:
            if t < b:
                return pname, t - a, b - a
        return None, 0, 0

    # --- phase renderers -------------------------------------------------

    def _terminal(self, frame, pt, dur):
        k = self.k
        x0, y0 = int(70 * k), int(90 * k)
        x1, y1 = self.w - int(70 * k), self.h - int(90 * k)
        overlay = frame.copy()
        cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.78, frame, 0.22, 0)
        cv2.rectangle(frame, (x0, y0), (x1, y1), DIM_GREEN, 1)
        cv2.putText(frame, "root@uplink:~", (x0 + int(12 * k), y0 - int(10 * k)),
                    cv2.FONT_HERSHEY_PLAIN, 1.3 * k, DIM_GREEN, 1, cv2.LINE_AA)

        font, scale = cv2.FONT_HERSHEY_PLAIN, 1.7 * k
        lh = int(38 * k)
        # Typing speed chosen so every line finishes at ~85% of the phase.
        progress_need = 0.18 * dur
        text_lines = [l for l in self.lines if l != "%PROGRESS%"]
        budget = 0.85 * dur - progress_need - 0.08 * len(text_lines)
        cps = sum(len(l) for l in text_lines) / max(budget, 0.1)
        t_left = pt
        y = y0 + int(45 * k)
        cursor = None
        for line in self.lines:
            if t_left <= 0:
                break
            if line == "%PROGRESS%":
                need = progress_need
                p = min(1.0, t_left / need)
                bars = int(p * 24)
                text = f"  [{'#' * bars}{'-' * (24 - bars)}] {int(p * 100):3d}%"
                t_left -= need
            else:
                n = int(t_left * cps)
                text = line[:n]
                t_left -= len(line) / cps + 0.08
            cv2.putText(frame, text, (x0 + int(20 * k), y), font, scale,
                        GREEN, 1, cv2.LINE_AA)
            tw = cv2.getTextSize(text, font, scale, 1)[0][0]
            cursor = (x0 + int(22 * k) + tw, y)
            y += lh
        if cursor and int(pt * 4) % 2 == 0:
            cx, cy = cursor
            cv2.rectangle(frame, (cx, cy - int(18 * k)), (cx + int(11 * k), cy + int(3 * k)),
                          GREEN, -1)
        return frame

    def _granted(self, frame, pt, dur):
        frame = cv2.convertScaleAbs(frame, alpha=0.3)
        flicker = pt < 0.35 * dur and int(pt * 30) % 3 == 0
        if not flicker:
            k = self.k
            cx, cy = self.w // 2, self.h // 2
            bw, bh = int(430 * k), int(70 * k)
            cv2.rectangle(frame, (cx - bw, cy - bh), (cx + bw, cy + bh), GREEN, 2)
            put_centered(frame, "ACCESS GRANTED", cy, cv2.FONT_HERSHEY_DUPLEX,
                         2.6 * k, max(2, int(4 * k)), GREEN, glow=True)
        intensity = max(0.15, 1.0 - pt / (0.6 * dur))
        return glitch(frame, intensity, self.rng)

    def _name(self, frame, pt, dur):
        k = self.k
        frame = cv2.convertScaleAbs(frame, alpha=0.25)
        put_centered(frame, "// IDENTITY CONFIRMED //", int(self.h * 0.30),
                     cv2.FONT_HERSHEY_PLAIN, 1.8 * k, 1, DIM_GREEN)
        type_time = 0.45 * dur
        total_chars = len(self.name) + len(self.title)
        n = int(min(1.0, pt / type_time) * total_chars)
        name = self.name[:n]
        title = self.title[:max(0, n - len(self.name))]
        if name:
            put_centered(frame, name.upper(), int(self.h * 0.47), cv2.FONT_HERSHEY_DUPLEX,
                         2.4 * k, max(2, int(3 * k)), GREEN, glow=True)
        if title:
            put_centered(frame, title, int(self.h * 0.60), cv2.FONT_HERSHEY_DUPLEX,
                         1.1 * k, max(1, int(2 * k)), DIM_GREEN)
        intensity = 0.5 * max(0.0, 1 - pt / type_time)
        if self.rng.random() < 0.06:  # occasional glitch burst
            intensity = 0.6
        return glitch(frame, intensity, self.rng)

    # --- main entry -------------------------------------------------------

    def render(self, t, cam_frame):
        """Frame for time t (seconds since start), or None when finished."""
        dt = max(0.0, min(0.1, t - self.last_t))
        self.last_t = t
        pname, pt, dur = self._phase(t)
        if pname is None:
            return None
        if pname == "transition":
            base = self.last_intro_frame if self.last_intro_frame is not None else cam_frame
            alpha = min(1.0, pt / dur)
            out = crossfade(base, cam_frame, alpha)
            out = glitch(out, 0.9 * (1 - alpha), self.rng)
            return scanlines(out, self.mask) if alpha < 0.85 else out

        frame = self.rain.step(dt)
        if pname == "terminal":
            frame = self._terminal(frame, pt, dur)
        elif pname == "granted":
            frame = self._granted(frame, pt, dur)
        elif pname == "name":
            frame = self._name(frame, pt, dur)
        frame = scanlines(frame, self.mask)
        self.last_intro_frame = frame
        return frame


# ---------------------------------------------------- live hacker filter ---

class HackerFilter:
    """Old-school hacker look for the live webcam: green phosphor monochrome,
    static noise, scanlines, a rolling VHS tracking band, RGB split and
    random glitch bursts with block corruption."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.k = h / 720
        self.rng = random.Random()
        self.mask = make_scanline_mask(w, h)
        self.noise = np.zeros((h, w), np.uint8)
        self.burst_until = 0.0

    def apply(self, frame, t):
        h, w = self.h, self.w
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        cv2.randu(self.noise, 0, 45)                      # static
        gray = cv2.add(gray, self.noise)
        # Phosphor green: B and R channels are dim copies of the luminance.
        out = cv2.merge([cv2.convertScaleAbs(gray, alpha=0.25), gray,
                         cv2.convertScaleAbs(gray, alpha=0.35)])

        # Rolling VHS tracking band.
        band_h = int(50 * self.k)
        y0 = int((t * 0.35 % 1.0) * (h + band_h)) - band_h
        ya, yb = max(0, y0), min(h, y0 + band_h)
        if yb > ya:
            out[ya:yb] = cv2.convertScaleAbs(out[ya:yb], alpha=1.25, beta=25)
            out[ya:yb] = np.roll(out[ya:yb], int(6 * self.k), axis=1)

        # Random glitch bursts on top of a constant light glitch.
        if t > self.burst_until and self.rng.random() < 0.025:
            self.burst_until = t + self.rng.uniform(0.08, 0.35)
        bursting = t < self.burst_until
        out = glitch(out, 0.75 if bursting else 0.12, self.rng)
        if bursting:  # displaced blocks ("datamosh" corruption)
            for _ in range(self.rng.randint(2, 6)):
                bw, bh = self.rng.randint(w // 16, w // 4), self.rng.randint(h // 30, h // 8)
                sx, sy = self.rng.randrange(0, w - bw), self.rng.randrange(0, h - bh)
                dx, dy = self.rng.randrange(0, w - bw), self.rng.randrange(0, h - bh)
                out[dy:dy + bh, dx:dx + bw] = out[sy:sy + bh, sx:sx + bw]

        out = scanlines(out, self.mask)

        # HUD
        k = self.k
        font = cv2.FONT_HERSHEY_PLAIN
        if int(t * 2) % 2 == 0:
            cv2.circle(out, (int(30 * k), int(30 * k)), int(8 * k), (60, 60, 255), -1)
        cv2.putText(out, "REC  [ SECURE CHANNEL ]", (int(48 * k), int(37 * k)),
                    font, 1.4 * k, GREEN, 1, cv2.LINE_AA)
        stamp = time.strftime("%H:%M:%S") + f"  0x{self.rng.getrandbits(24):06X}"
        cv2.putText(out, stamp, (int(20 * k), h - int(20 * k)),
                    font, 1.3 * k, DIM_GREEN, 1, cv2.LINE_AA)
        return out


# ------------------------------------------------------------ vision (ML) ---

# Inside a packaged app (PyInstaller) bundled files live under sys._MEIPASS.
FROZEN = getattr(sys, "frozen", False)
MODEL_DIR = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
                         "models")


def user_data_dir():
    """Writable per-user folder (used by the packaged app for downloads)."""
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(base, "HackerCam")
MODEL_URLS = {
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/"
                            "face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
    "selfie_segmenter.tflite": "https://storage.googleapis.com/mediapipe-models/"
                               "image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite",
}


def model_path(name):
    """Path to a MediaPipe model, downloading it on first use if missing.
    The packaged app ships the models; it never writes inside itself."""
    path = os.path.join(MODEL_DIR, name)
    if os.path.exists(path):
        return path
    target_dir = os.path.join(user_data_dir(), "models") if FROZEN else MODEL_DIR
    path = os.path.join(target_dir, name)
    if not os.path.exists(path):
        os.makedirs(target_dir, exist_ok=True)
        print(f"[+] Downloading model {name} (one time) ...")
        urllib.request.urlretrieve(MODEL_URLS[name], path + ".part")
        os.replace(path + ".part", path)
    return path


class Vision:
    """Lazily loaded MediaPipe tasks: person segmentation and face landmarks.
    Every method returns None when mediapipe or a model is unavailable."""

    def __init__(self):
        self._tasks = {}
        self._failed = set()
        self._ts = 0
        self._lock = threading.Lock()
        self.tessellation = None  # (M, 2) landmark index pairs of the face mesh

    def preload(self):
        """Load both models on a background thread so the first toggle doesn't stutter."""
        threading.Thread(target=lambda: (self._get("seg"), self._get("face")), daemon=True).start()

    def _next_ts(self):
        # VIDEO-mode tasks need strictly increasing timestamps (ms).
        self._ts = max(self._ts + 1, int(time.monotonic() * 1000))
        return self._ts

    def _get(self, kind):
        if kind in self._tasks:
            return self._tasks[kind]
        with self._lock:
            return self._load(kind)

    def _load(self, kind):
        if kind in self._tasks:
            return self._tasks[kind]
        if kind in self._failed:
            return None
        try:
            os.environ.setdefault("GLOG_minloglevel", "2")
            from mediapipe.tasks.python import BaseOptions, vision
            if kind == "seg":
                task = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
                    base_options=BaseOptions(model_asset_path=model_path("selfie_segmenter.tflite")),
                    running_mode=vision.RunningMode.VIDEO,
                    output_confidence_masks=True, output_category_mask=False))
            else:
                task = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=model_path("face_landmarker.task")),
                    running_mode=vision.RunningMode.VIDEO, num_faces=1))
                self.tessellation = np.array(
                    [(c.start, c.end) for c in
                     vision.FaceLandmarksConnections.FACE_LANDMARKS_TESSELATION], np.int32)
        except Exception as e:  # ImportError, download failure, ...
            print(f"[!] {'Segmentation' if kind == 'seg' else 'Face tracking'} unavailable: {e}\n"
                  "    Install it with: pip install mediapipe")
            self._failed.add(kind)
            return None
        self._tasks[kind] = task
        return task

    def close(self):
        """Release the MediaPipe tasks now, not during interpreter shutdown
        (where their destructors fail noisily)."""
        with self._lock:
            tasks, self._tasks = self._tasks, {}
            self._failed.update(tasks)        # don't reload after closing
        for task in tasks.values():
            try:
                task.close()
            except Exception:
                pass

    @staticmethod
    def _mp_image(frame):
        import mediapipe as mp
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    def segment(self, frame):
        """Person probability mask (float32, 0..1) at the frame's half size."""
        task = self._get("seg")
        if task is None:
            return None
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
        res = task.segment_for_video(self._mp_image(small), self._next_ts())
        mask = np.squeeze(res.confidence_masks[0].numpy_view()).astype(np.float32)
        if mask.shape != small.shape[:2]:
            mask = cv2.resize(mask, (small.shape[1], small.shape[0]))
        return mask

    def face(self, frame):
        """(N, 2) float32 pixel coordinates of face landmarks, or None."""
        task = self._get("face")
        if task is None:
            return None
        res = task.detect_for_video(self._mp_image(frame), self._next_ts())
        if not res.face_landmarks:
            return None
        h, w = frame.shape[:2]
        return np.array([(p.x * w, p.y * h) for p in res.face_landmarks[0]], np.float32)


# ------------------------------------------------ person mask + compositing ---

CYAN = (255, 225, 80)          # BGR


def tint(gray, color):
    """Single-channel uint8 image -> BGR image coloured by `color`."""
    return cv2.merge([cv2.convertScaleAbs(gray, alpha=c / 255) for c in color])


class PersonMask:
    """Person segmentation, updated once per frame and shared by every effect.
    Kept at half resolution with temporal smoothing to stop edge flicker."""

    def __init__(self, w, h, vision):
        self.w, self.h, self.vision = w, h, vision
        self.half = None
        self.soft = None
        self._full = self._rim = None

    def update(self, raw):
        m = self.vision.segment(raw)
        if m is None:
            return False
        if self.half is None or self.half.shape != m.shape:
            self.half = m
        else:
            self.half = cv2.addWeighted(self.half, 0.5, m, 0.5, 0)
        self.soft = cv2.GaussianBlur(self.half, (0, 0), 2)
        self._full = self._rim = None
        return True

    def reset(self):
        self.half = None

    def full(self):
        """Float32 person alpha (0..1) at output resolution."""
        if self._full is None:
            self._full = cv2.resize(self.soft, (self.w, self.h))
        return self._full

    def rim(self):
        """uint8 glow band just outside the person's outline."""
        if self._rim is None:
            r = np.clip((cv2.GaussianBlur(self.soft, (0, 0), 9) - self.soft) * 2.2, 0, 1)
            self._rim = cv2.resize(cv2.convertScaleAbs(r, alpha=255), (self.w, self.h))
        return self._rim


def composite(person, bg, alpha, rim=None, rim_color=GREEN):
    out = cv2.blendLinear(person, bg, alpha, 1 - alpha)
    return out if rim is None else cv2.add(out, tint(rim, rim_color))


# ------------------------------------------------------ matrix background ---

class MatrixBackground:
    """Matrix rain used as a virtual background."""

    def __init__(self, w, h):
        self.rain = Rain(w, h, random.Random(), cell=max(10, int(16 * h / 720))).warm()
        self.last = time.monotonic()

    def render(self, now):
        dt, self.last = min(0.1, now - self.last), now
        return self.rain.step(dt)


# ------------------------------------------------------------- hologram ---

class Hologram:
    """You as a translucent, flickering cyan hologram projected into the room."""

    def __init__(self, w, h):
        self.w, self.h, self.k = w, h, h / 720
        self.rng = random.Random()
        # Rolling scanline pattern (2 dark rows in every 5), sliced per frame.
        rows = np.where(np.arange(h + 5) % 5 < 2, 110, 255).astype(np.uint16)
        self.pattern = rows[:, None]
        # Projector glow at the bottom centre.
        glow = np.zeros((h, w), np.uint8)
        cv2.ellipse(glow, (w // 2, h + int(10 * self.k)), (int(w * 0.32), int(90 * self.k)),
                    0, 0, 360, 255, -1)
        self.emitter = tint(cv2.GaussianBlur(glow, (0, 0), 40 * self.k), CYAN)
        self.flicker = 1.0

    def background(self, base):
        """Darken whatever is behind you so the projection reads."""
        return cv2.add(cv2.convertScaleAbs(base, alpha=0.35), cv2.convertScaleAbs(self.emitter, alpha=0.6))

    def person(self, raw, t):
        gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
        gray = cv2.convertScaleAbs(gray, alpha=1.35, beta=30)
        off = int(t * 40) % 5
        gray = (gray.astype(np.uint16) * self.pattern[off:off + self.h] // 255).astype(np.uint8)
        r = self.rng.random()
        self.flicker = 0.55 if r < 0.03 else 0.85 + 0.15 * self.rng.random()
        layer = tint(gray, CYAN)
        return glitch(layer, 0.3 if r < 0.07 else 0.04, self.rng)

    def opacity(self):
        return 0.8 * self.flicker

    def hud(self, frame, t):
        k = self.k
        font = cv2.FONT_HERSHEY_PLAIN
        signal = 96 + 3 * self.rng.random()
        cv2.putText(frame, f"HOLO-LINK // SIGNAL {signal:4.1f}%", (int(20 * k), self.h - int(20 * k)),
                    font, 1.3 * k, CYAN, 1, cv2.LINE_AA)
        if int(t * 2) % 2 == 0:
            text = "PROJECTION ACTIVE"
            tw = cv2.getTextSize(text, font, 1.3 * k, 1)[0][0]
            cv2.putText(frame, text, (self.w - tw - int(20 * k), int(34 * k)),
                        font, 1.3 * k, CYAN, 1, cv2.LINE_AA)
        return frame


# --------------------------------------------------------- global trace ---

# Natural Earth 1:110m land (public domain), rasterised to 180x90 two-degree
# cells, bit-packed, zlib-compressed, base64. Row 0 = 90N, column 0 = 180W.
LAND_BITS = (
    "eNq9Vb1uFDEQHt+G7CEd2ZQpIjaijpRINJE4sSl4kEg0lFdBChQ7pAgVLwDi50nOCJQ0hDwAxa1CkXRYAnErnWPj"
    "Gf/sHlwHYoq92c/fzs/nsQ/gH1lpmK3/QCvrDOE9gLTae4JoA6V0L7kMaL49/epgoq5CEeHypQZuFbo7wA2sC0LP"
    "piqzBt3BkksiJfQzCZNzXleYbwfeYw6r4dA9zfXk0LlQNTdtsJJKOCgbl9h+i+hder6ROqvZLIJWEfnVsHCpOU8w"
    "o95uwz5AcRnBscjfuoTsB5Z2UAX0EmDo6Lp0pbGj04CCggEU1s6sCzy8F1C5gp+6NGNX8XIqTaIgGXmu/Yhqr5Hz"
    "TtxvKm2XYFzfxv6CUU2YkHaE2/E5oiaRCf2ihkR+Eckocn7heqB2RSSj8/TOxKAen/p+By3tU/b6gZ1i4IeezHFT"
    "XZGqR4FPaC+B+Xy5fU7NmDUICXX4xsbRoYRXMpQ+sb4ktBt6yUcyJghDtiXi6P3skGF/JSjIlXtsxLE72fH5ZjbX"
    "KQQM5ciTx3V1fBVRpkPkazchvJdg5bu3E1hnTYwMeexEMFkepTOx2vjIUxiw0VqCUbuSWq5XmUihUWjqogeiJZdO"
    "0vyUWt5sUeYOFa65KrMPonMIBWV07vosoTkpQ6cFTt+JlqwxEDa6/HgrHU7a2oL02di+v9sebywPyaxmKqAZHu5A"
    "hke3nqWasQKu528IPweFvaCXjxEuqDqr9/DFPyGWW9jP/sYBFmNoErCm5KoVSWLlAz+xQnRF4kpGqQIZvdwMfEky"
    "tYIer324NEoVkjPdmWNPxhSl+J2s4ogANDxFNq0GfZbKSOskglgK8quuZLsQ9DjoohkMArkbAtIs7c/rPoopFt7m"
    "TXTmlov+QvJoIZoJ+L/WWwwHNapwuIJt+hrH9tj/FwXp6nDHfqfbx4T94wFtLyUefjtoA8xf1HNcN/J0yyoY2Tly"
    "+LSsOqjpXNYd04X9e/sFC3zTQQ=="
)

CITIES = [
    ("NEW YORK", 40.7, -74.0), ("SAN FRANCISCO", 37.8, -122.4), ("TORONTO", 43.7, -79.4),
    ("MEXICO CITY", 19.4, -99.1), ("SAO PAULO", -23.5, -46.6), ("REYKJAVIK", 64.1, -21.9),
    ("LONDON", 51.5, -0.1), ("AMSTERDAM", 52.4, 4.9), ("FRANKFURT", 50.1, 8.7),
    ("STOCKHOLM", 59.3, 18.1), ("MOSCOW", 55.8, 37.6), ("CAIRO", 30.0, 31.2),
    ("LAGOS", 6.5, 3.4), ("JOHANNESBURG", -26.2, 28.0), ("DUBAI", 25.2, 55.3),
    ("MUMBAI", 19.1, 72.9), ("BANGALORE", 13.0, 77.6), ("SINGAPORE", 1.35, 103.8),
    ("HONG KONG", 22.3, 114.2), ("SEOUL", 37.6, 127.0), ("TOKYO", 35.7, 139.7),
    ("SYDNEY", -33.9, 151.2),
]


def land_mask():
    import base64
    import zlib
    bits = np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode("".join(LAND_BITS))), np.uint8))
    return bits[:180 * 90].reshape(90, 180).astype(bool)


class GlobalTrace:
    """Virtual background: a dot-matrix world map with a live network trace
    hopping between cities, then TRACE COMPLETE, then a new route."""

    LAT_TOP, LAT_BOTTOM = 78.0, -58.0
    HOPS, HOP_TIME, HOLD = 7, 1.15, 2.6

    def __init__(self, w, h):
        self.w, self.h, self.k = w, h, h / 720
        self.rng = random.Random()
        self.base = self._draw_map()
        self.t0 = None
        self.last = 0.0
        self.latency = 120.0

    def project(self, lat, lon):
        x = (lon + 180) / 360 * self.w
        y = (self.LAT_TOP - lat) / (self.LAT_TOP - self.LAT_BOTTOM) * self.h
        return np.array([x, y], np.float32)

    def _draw_map(self):
        w, h, k = self.w, self.h, self.k
        img = np.full((h, w, 3), (12, 10, 6), np.uint8)
        for lon in range(-180, 181, 30):
            x = int(self.project(0, lon)[0])
            cv2.line(img, (x, 0), (x, h), (30, 38, 22), 1)
        for lat in range(-60, 90, 30):
            y = int(self.project(lat, 0)[1])
            cv2.line(img, (0, y), (w, y), (30, 38, 22), 1)
        land = land_mask()
        r = max(1, int(round(1.8 * k)))
        for row, col in zip(*np.nonzero(land)):
            lat, lon = 89 - row * 2, -179 + col * 2
            if self.LAT_BOTTOM <= lat <= self.LAT_TOP:
                x, y = self.project(lat, lon)
                cv2.circle(img, (int(x), int(y)), r, (45, 120, 45), -1, cv2.LINE_AA)
        return img

    def _new_route(self):
        self.route = self.rng.sample(CITIES, self.HOPS + 1)
        self.ips = [".".join(str(self.rng.randint(11, 254)) for _ in range(4)) for _ in self.route]

    @staticmethod
    def _arc(p0, p1, n=48):
        mid = (p0 + p1) / 2
        d = np.linalg.norm(p1 - p0)
        ctrl = mid - np.array([0, d * 0.35], np.float32)      # bow upwards
        s = np.linspace(0, 1, n, dtype=np.float32)[:, None]
        return ((1 - s) ** 2 * p0 + 2 * (1 - s) * s * ctrl + s ** 2 * p1)

    def render(self, now):
        if self.t0 is None or now - self.last > 1.0:   # (re)started
            self.t0 = now
            self._new_route()
        self.last = now
        k = self.k
        cycle = self.HOPS * self.HOP_TIME + self.HOLD
        t = now - self.t0
        if t >= cycle:
            self.t0 = now
            self._new_route()
            t = 0.0
        fade = min(1.0, (cycle - t) / 0.5)

        frame = self.base.copy()
        ov = np.zeros_like(frame)
        font = cv2.FONT_HERSHEY_PLAIN
        pts = [self.project(lat, lon) for _, lat, lon in self.route]
        hops_done = min(self.HOPS, int(t / self.HOP_TIME))
        traveling = t < self.HOPS * self.HOP_TIME

        for i in range(self.HOPS):
            start = i * self.HOP_TIME
            if t < start:
                break
            arc = self._arc(pts[i], pts[i + 1])
            p = min(1.0, (t - start) / (self.HOP_TIME * 0.75))
            n = max(2, int(p * len(arc)))
            seg = arc[:n].astype(np.int32)
            done = p >= 1.0
            cv2.polylines(ov, [seg], False, DIM_GREEN if done else GREEN, max(1, int(2 * k)), cv2.LINE_AA)
            if not done:
                hx, hy = seg[-1]
                cv2.circle(ov, (int(hx), int(hy)), int(5 * k), HEAD_COLOR, -1, cv2.LINE_AA)
            else:  # arrival pulse
                age = t - start - self.HOP_TIME * 0.75
                if age < 0.8:
                    rad = int((6 + 30 * age / 0.8) * k)
                    col = tuple(int(c * (1 - age / 0.8)) for c in GREEN)
                    cv2.circle(ov, tuple(int(v) for v in pts[i + 1]), rad, col, max(1, int(2 * k)), cv2.LINE_AA)

        # Nodes and labels for every city reached so far (plus the source).
        reached = hops_done + 1 if traveling else self.HOPS + 1
        for i in range(reached):
            x, y = (int(v) for v in pts[i])
            final = not traveling and i == self.HOPS
            color = AMBER if final else (GREEN if i else CYAN)
            cv2.circle(ov, (x, y), int(4 * k), color, -1, cv2.LINE_AA)
            label = "SRC" if i == 0 else ("TARGET" if final else f"HOP {i}")
            cv2.putText(ov, f"{label} {self.route[i][0]}", (x + int(8 * k), y - int(6 * k)),
                        font, 1.0 * k, color, 1, cv2.LINE_AA)
            cv2.putText(ov, self.ips[i], (x + int(8 * k), y + int(10 * k)),
                        font, 0.9 * k, DIM_GREEN, 1, cv2.LINE_AA)
        if not traveling:  # target lock rings
            x, y = (int(v) for v in pts[-1])
            rad = int((14 + 6 * np.sin(t * 8)) * k)
            cv2.circle(ov, (x, y), rad, AMBER, max(1, int(2 * k)), cv2.LINE_AA)
            cv2.circle(ov, (x, y), rad * 2, AMBER, 1, cv2.LINE_AA)

        frame = cv2.add(frame, cv2.add(ov, cv2.GaussianBlur(ov, (0, 0), 5 * k)))

        # Status panel, top left.
        self.latency = float(np.clip(self.latency + self.rng.uniform(-9, 9), 40, 380))
        status = "TRACING..." if traveling else "LOCATED"
        lines = [("GLOBAL TRACE // ACTIVE", GREEN), (f"HOPS     {hops_done}/{self.HOPS}", GREEN),
                 (f"LATENCY  {int(self.latency):3d} ms", GREEN), ("ROUTE    ONION x3", DIM_GREEN),
                 (f"STATUS   {status}", AMBER if not traveling else GREEN)]
        x0, y0 = int(18 * k), int(18 * k)
        pw, ph = int(300 * k), int(30 * k) * len(lines) + int(16 * k)
        frame[y0:y0 + ph, x0:x0 + pw] = cv2.convertScaleAbs(frame[y0:y0 + ph, x0:x0 + pw], alpha=0.3)
        cv2.rectangle(frame, (x0, y0), (x0 + pw, y0 + ph), DIM_GREEN, 1)
        for i, (text, color) in enumerate(lines):
            cv2.putText(frame, text, (x0 + int(12 * k), y0 + int(30 * k) * (i + 1)),
                        font, 1.25 * k, color, 1, cv2.LINE_AA)
        if not traveling and int(t * 3) % 2 == 0:
            put_centered(frame, "TRACE COMPLETE", int(self.h * 0.9), cv2.FONT_HERSHEY_DUPLEX,
                         1.2 * k, max(1, int(2 * k)), AMBER)
        return frame if fade >= 1 else cv2.convertScaleAbs(frame, alpha=0.4 + 0.6 * fade)


# -------------------------------------------------------- entrance effect ---

class Entrance:
    """You assemble out of falling particles on black (or onto the active
    virtual background); then the room fades in. 'armed' holds the empty
    screen with INCOMING SIGNAL until triggered."""

    START, ASSEMBLE, ROOM = 0.15, 2.6, 0.7   # seconds
    BAND = 0.16                               # flight window in noise units

    def __init__(self, w, h):
        self.w, self.h, self.k = w, h, h / 720
        self.rng = random.Random()
        self.state = "idle"                   # idle | armed | playing
        self.t0 = self.last = 0.0
        s = max(3, int(4 * self.k))
        self.step = s
        gy, gx = np.mgrid[s // 2:h:s, s // 2:w:s]
        self.gx, self.gy = gx.ravel(), gy.ravel()

    @property
    def active(self):
        return self.state != "idle"

    def arm(self):
        self.state = "armed"

    def trigger(self, now):
        nr = np.random.default_rng()
        w, h = self.w, self.h
        noise = (cv2.resize(nr.random((9, 16), np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
                 + 0.4 * cv2.resize(nr.random((36, 64), np.float32), (w, h), interpolation=cv2.INTER_CUBIC))
        noise = (noise - noise.min()) / (noise.max() - noise.min())
        ramp = np.linspace(0, 1, h, dtype=np.float32)[:, None]   # head first
        n = 0.55 * noise + 0.45 * ramp
        self.noise = ((n - n.min()) / (n.max() - n.min())).astype(np.float32)
        self.gnoise = self.noise[self.gy, self.gx]
        cnt = len(self.gx)
        self.off_x = (nr.normal(0, 1, cnt) * 220 * self.k).astype(np.float32)
        self.off_y = (-np.abs(nr.normal(0, 1, cnt)) * 260 * self.k - 40 * self.k).astype(np.float32)
        self.range = None                     # noise range covered by you, set on first frame
        self.state, self.t0 = "playing", now

    def render(self, frame, empty, mask, now):
        """frame: the finished frame; empty: the scene without you (None = black);
        mask: float person alpha or None."""
        if empty is None:
            empty = np.zeros_like(frame)
        if self.state == "armed":
            out = empty.copy()
            if int(now * 1.5) % 2 == 0:
                put_centered(out, "INCOMING SIGNAL ...", int(self.h * 0.92), cv2.FONT_HERSHEY_PLAIN,
                             1.5 * self.k, 1, DIM_GREEN)
            return out
        t = now - self.t0
        if t >= self.START + self.ASSEMBLE + self.ROOM:
            self.state = "idle"
            return frame
        if mask is None:
            mask = np.ones((self.h, self.w), np.float32)
        # Time the reveal over the noise values *you* cover, not the whole
        # frame: otherwise nothing happens at first and it stalls at the end.
        if self.range is None:
            vals = self.noise[mask > 0.5]
            self.range = ((float(np.percentile(vals, 1)), float(np.percentile(vals, 99)))
                          if vals.size > 1000 else (0.0, 1.0))
        lo, hi = self.range
        prog = min(max((t - self.START) / self.ASSEMBLE, 0.0), 1.0)
        p = lo - self.BAND + prog * (hi - lo + self.BAND)   # ends as you're complete

        # Pixels whose noise threshold has been passed are "assembled".
        reveal = np.clip((p - self.noise) / 0.03, 0, 1) * mask
        room = np.clip((t - self.START - self.ASSEMBLE) / self.ROOM, 0, 1)
        alpha = np.maximum(reveal, room).astype(np.float32)
        out = cv2.blendLinear(frame, empty, alpha, 1 - alpha)

        # Bright seam where pixels are materialising right now.
        seam = np.clip(1 - np.abs(p - self.noise) / 0.025, 0, 1) * mask
        out = cv2.add(out, tint(cv2.convertScaleAbs(seam, alpha=255), GREEN))

        # Particles still in flight towards their pixel.
        gm = mask[self.gy, self.gx] > 0.5
        f = (self.gnoise - p) / self.BAND
        sel = gm & (f > 0) & (f < 1)
        if sel.any():
            fs = f[sel]
            ease = fs ** 1.6
            tx, ty = self.gx[sel], self.gy[sel]
            px = (tx + self.off_x[sel] * ease).astype(np.int32)
            py = (ty + self.off_y[sel] * ease).astype(np.int32)
            target_col = frame[ty, tx].astype(np.float32)
            col = target_col * (1 - fs[:, None]) + np.array(HEAD_COLOR, np.float32) * fs[:, None] * 0.6 \
                + np.array(GREEN, np.float32) * fs[:, None] * 0.4
            col = col.astype(np.uint8)
            sz = max(2, self.step - 1)
            for dy in range(sz):
                for dx in range(sz):
                    xx, yy = px + dx, py + dy
                    ok = (xx >= 0) & (xx < self.w) & (yy >= 0) & (yy < self.h)
                    out[yy[ok], xx[ok]] = col[ok]
        return out


# --------------------------------------------------------- biometric scan ---

def draw_brackets(img, x0, y0, x1, y1, color, length, thickness):
    for (x, y, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        cv2.line(img, (x, y), (x + dx * length, y), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x, y), (x, y + dy * length), color, thickness, cv2.LINE_AA)


class BiometricScan:
    """One-shot (~5 s) face scan: lock-on brackets, a laser sweep that reveals
    the face mesh, a checklist panel, then a BIOMETRIC MATCH result."""

    LOCK, SWEEP_END, RESULT, DURATION = 0.6, 2.6, 3.2, 5.0
    CHECKS = [("FACIAL GEOMETRY", "{n} PTS"), ("IRIS PATTERN", "LOCKED"),
              ("LIVENESS", "CONFIRMED"), ("DB QUERY", "MATCH")]

    def __init__(self, w, h, name, vision):
        self.w, self.h, self.name, self.vision = w, h, name, vision
        self.k = h / 720
        self.match = f"{random.uniform(99.1, 99.9):.1f}%"
        self.box = None
        self.lm = None

    def _track(self, raw):
        lm = self.vision.face(raw)
        if lm is None:
            return
        self.lm = lm
        (x0, y0), (x1, y1) = lm.min(0), lm.max(0)
        pw, ph = (x1 - x0) * 0.18, (y1 - y0) * 0.15
        box = np.array([x0 - pw, y0 - ph * 1.5, x1 + pw, y1 + ph], np.float32)
        self.box = box if self.box is None else self.box * 0.6 + box * 0.4

    def _panel(self, out, box, t):
        k = self.k
        font = cv2.FONT_HERSHEY_PLAIN
        if t < self.RESULT:
            pct = int(np.clip((t - self.LOCK) / (self.SWEEP_END - self.LOCK), 0, 1) * 100)
            lines = [("BIOMETRIC SCAN", AMBER, 1.6), (f"PROGRESS {pct:3d}%", AMBER, 1.3), ("", None, 1)]
            for i, (label, status) in enumerate(self.CHECKS):
                shown_at = 1.0 + i * 0.55
                if t < shown_at:
                    break
                done = t > shown_at + 0.3
                n = len(self.lm) if self.lm is not None else 0
                lines.append((f"{label:<16}" + (status.format(n=n) if done else "..."),
                              GREEN if done else DIM_GREEN, 1.25))
        else:
            lines = [(f"BIOMETRIC MATCH {self.match}", GREEN, 1.8), ("", None, 1),
                     (f"IDENTITY   {self.name.upper()}", GREEN, 1.35),
                     ("CLEARANCE  LEVEL 5", GREEN, 1.35),
                     ("STATUS     AUTHORIZED", GREEN, 1.35)]
        lh = int(30 * k)
        pw = max(cv2.getTextSize(s, font, sc * k, 1)[0][0] for s, _, sc in lines) + int(32 * k)
        ph = lh * len(lines) + int(24 * k)
        x0, y0, x1, y1 = box
        gap = int(24 * k)
        px = x1 + gap if x1 + gap + pw < self.w - 10 else x0 - gap - pw
        px = int(np.clip(px, 10, max(10, self.w - pw - 10)))
        py = int(np.clip(y0, 10, max(10, self.h - ph - 10)))
        roi = out[py:py + ph, px:px + pw]
        out[py:py + ph, px:px + pw] = cv2.convertScaleAbs(roi, alpha=0.25)
        border = GREEN if t >= self.RESULT else AMBER
        cv2.rectangle(out, (px, py), (px + pw, py + ph), border, 1, cv2.LINE_AA)
        y = py + int(34 * k)
        for text, color, sc in lines:
            if text:
                cv2.putText(out, text, (px + int(16 * k), y), font, sc * k, color, 1, cv2.LINE_AA)
            y += lh

    def render(self, frame, raw, t):
        """Overlay the scan at t seconds; returns None when finished."""
        if t >= self.DURATION:
            return None
        self._track(raw)
        k, w, h = self.k, self.w, self.h
        box = self.box if self.box is not None else np.array(
            [w * 0.35, h * 0.15, w * 0.65, h * 0.85], np.float32)
        if t < self.LOCK:  # brackets zoom in onto the face
            s = 1 + 0.7 * (1 - t / self.LOCK) ** 2
            c = (box[:2] + box[2:]) / 2
            half = (box[2:] - box[:2]) / 2 * s
            box = np.concatenate([c - half, c + half])
        x0, y0, x1, y1 = [int(v) for v in box]

        ov = np.zeros_like(frame)
        color = AMBER if t < self.RESULT else GREEN
        draw_brackets(ov, x0, y0, x1, y1, color, int(30 * k), max(2, int(3 * k)))

        sweep = np.clip((t - self.LOCK) / (self.SWEEP_END - self.LOCK), 0, 1)
        line_y = y0 + (y1 - y0) * sweep
        if self.lm is not None and t >= self.LOCK:
            mesh_a = 1.0 if t < self.RESULT else max(0.25, 1 - (t - self.RESULT) / 0.8)
            tess = self.vision.tessellation
            if tess is not None:
                segs = self.lm[tess]                          # (M, 2, 2)
                segs = segs[segs[:, :, 1].max(1) < line_y].astype(np.int32)
                mesh_color = tuple(int(c * 0.45 * mesh_a) for c in GREEN)
                if len(segs):
                    cv2.polylines(ov, list(segs), False, mesh_color, 1, cv2.LINE_AA)
            pts = self.lm[::3]
            dot_color = tuple(int(c * mesh_a) for c in GREEN)
            for x, y in pts[pts[:, 1] < line_y].astype(int):
                cv2.circle(ov, (x, y), 1, dot_color, -1)

        if self.LOCK <= t < self.SWEEP_END:  # laser line with a fading trail
            ly = int(line_y)
            for i in range(10):
                yy = ly - int(i * 4 * k)
                fade = 0.4 * (1 - i / 10)
                cv2.line(ov, (x0, yy), (x1, yy), tuple(int(c * fade) for c in GREEN), 1)
            cv2.line(ov, (x0 - int(20 * k), ly), (x1 + int(20 * k), ly), HEAD_COLOR, 2, cv2.LINE_AA)

        out = cv2.add(frame, cv2.add(ov, cv2.GaussianBlur(ov, (0, 0), 6 * k)))
        self._panel(out, (x0, y0, x1, y1), t)
        fade = min(1.0, (self.DURATION - t) / 0.5)
        return out if fade >= 1 else cv2.addWeighted(out, fade, frame, 1 - fade, 0)


# ------------------------------------------------------------ away screen ---

def scramble(frame, p, rng):
    """Dissolve a frame into big pixels and hex blocks; p in 0..1."""
    if p <= 0.01:
        return frame
    h, w = frame.shape[:2]
    b = int(4 + p * 44)
    small = cv2.resize(frame, (max(1, w // b), max(1, h // b)), interpolation=cv2.INTER_AREA)
    out = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    green = cv2.merge([gray // 5, gray, gray // 4])
    out = crossfade(out, green, p)
    cols, rows = w // b + 1, h // b + 1
    scale = b / 24
    for _ in range(min(500, int(p * cols * rows * 0.5))):
        x, y = rng.randrange(cols) * b, rng.randrange(rows) * b
        out[y:y + b, x:x + b] = 0
        cv2.putText(out, f"{rng.getrandbits(8):02X}", (x + 2, y + int(b * 0.7)),
                    cv2.FONT_HERSHEY_PLAIN, scale, GREEN, 1)
    return glitch(out, 0.6 * p, rng)


def draw_padlock(img, cx, cy, s, color):
    t = max(2, int(0.1 * s))
    cv2.ellipse(img, (cx, cy - int(0.1 * s)), (int(0.3 * s), int(0.4 * s)), 0, 180, 360,
                color, t, cv2.LINE_AA)
    cv2.rectangle(img, (cx - int(0.45 * s), cy - int(0.1 * s)),
                  (cx + int(0.45 * s), cy + int(0.55 * s)), color, -1)
    cv2.circle(img, (cx, cy + int(0.17 * s)), int(0.08 * s), (0, 0, 0), -1)
    cv2.rectangle(img, (cx - int(0.03 * s), cy + int(0.17 * s)),
                  (cx + int(0.03 * s), cy + int(0.36 * s)), (0, 0, 0), -1)


class AwayScreen:
    """Toggle: the live feed scrambles into an encrypted 'session suspended'
    screen with an away timer; toggling again decrypts back to you."""

    TRANS = 0.8

    def __init__(self, w, h):
        self.w, self.h, self.k = w, h, h / 720
        self.state = "off"            # off | entering | on | leaving
        self.t0 = self.since = 0.0
        self.rng = random.Random()
        self.rain = Rain(w, h, self.rng, cell=max(10, int(16 * self.k))).warm()
        self.mask = make_scanline_mask(w, h)
        self.last = time.monotonic()

    @property
    def covering(self):
        """True when the live feed is fully hidden (no need to process it)."""
        return self.state == "on"

    def toggle(self, now):
        if self.state in ("off", "leaving"):
            if self.state == "off":
                self.since = now
            self.state = "entering"
        else:
            self.state = "leaving"
        self.t0 = now

    def _screen(self, now):
        k, w, h = self.k, self.w, self.h
        dt, self.last = min(0.1, now - self.last), now
        out = cv2.convertScaleAbs(self.rain.step(dt), alpha=0.3)
        draw_padlock(out, w // 2, int(h * 0.27), int(90 * k), GREEN)
        put_centered(out, "SESSION SUSPENDED", int(h * 0.50), cv2.FONT_HERSHEY_DUPLEX,
                     1.9 * k, max(2, int(3 * k)), GREEN, glow=True)
        put_centered(out, "USER AWAY  //  CHANNEL ENCRYPTED (AES-256-GCM)", int(h * 0.60),
                     cv2.FONT_HERSHEY_PLAIN, 1.6 * k, 1, DIM_GREEN)
        secs = int(now - self.since)
        put_centered(out, f"AWAY  {secs // 3600:02d}:{secs // 60 % 60:02d}:{secs % 60:02d}",
                     int(h * 0.70), cv2.FONT_HERSHEY_DUPLEX, 1.2 * k, max(1, int(2 * k)), GREEN)
        cursor = "_" if int(now * 2) % 2 == 0 else " "
        put_centered(out, f"> awaiting re-authentication{cursor}", int(h * 0.80),
                     cv2.FONT_HERSHEY_PLAIN, 1.4 * k, 1, DIM_GREEN)
        return scanlines(out, self.mask)

    def render(self, frame, now):
        if self.state == "off":
            return frame
        p = min(1.0, (now - self.t0) / self.TRANS)
        if self.state == "on":
            return self._screen(now)
        if self.state == "entering":
            if p >= 1:
                self.state = "on"
                return self._screen(now)
            return crossfade(scramble(frame, p, self.rng), self._screen(now),
                             max(0.0, p * 2 - 1))
        # leaving
        if p >= 1:
            self.state = "off"
            return frame
        return crossfade(self._screen(now), scramble(frame, 1 - p, self.rng),
                         min(1.0, p * 2))


# ----------------------------------------------------------------- webcam ---

class Webcam:
    """Reads the real webcam on a background thread; keeps the latest frame."""

    def __init__(self, index, w, h, log=print):
        self.w, self.h = w, h
        self.lock = threading.Lock()
        self.frame = None
        self.running = True
        self.standby = self._standby_frame()
        self.cap = cv2.VideoCapture(index)
        self.ok = self.cap.isOpened()
        if not self.ok:
            log(f"[!] Could not open webcam index {index}; showing standby screen.")
            self.cap = None
            return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        threading.Thread(target=self._loop, daemon=True).start()

    def _standby_frame(self):
        f = np.zeros((self.h, self.w, 3), np.uint8)
        put_centered(f, "[ CAMERA OFFLINE ]", self.h // 2, cv2.FONT_HERSHEY_DUPLEX,
                     1.6 * self.h / 720, 2, DIM_GREEN)
        return scanlines(f, make_scanline_mask(self.w, self.h))

    def _loop(self):
        while self.running:
            ok, f = self.cap.read()
            if not ok:
                time.sleep(0.02)
                continue
            f = resize_cover(f, self.w, self.h)
            with self.lock:
                self.frame = f

    def get(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else self.standby.copy()

    def close(self):
        self.running = False
        if self.cap is not None:
            time.sleep(0.05)
            self.cap.release()


# ---------------------------------------------------------------- hotkeys ---

# Hotkey letter -> action. All are Ctrl+Alt+<letter>.
HOTKEYS = {"h": "replay", "g": "filter", "m": "matrix", "t": "trace", "o": "hologram",
           "b": "scan", "e": "entrance", "a": "away", "q": "quit"}
# macOS ANSI virtual key codes: Option+letter types a symbol (Option+H = "˙"),
# so on macOS letters are matched by physical key code instead of character.
MAC_VK = {0: "a", 11: "b", 14: "e", 5: "g", 4: "h", 46: "m", 31: "o", 12: "q", 17: "t"}


def start_hotkeys(events):
    """Global Ctrl+Alt+<letter> hotkeys that set events[action]."""
    try:
        from pynput import keyboard
    except Exception as e:
        print(f"[!] Global hotkeys unavailable ({e}). Use the preview window keys or Ctrl+C.")
        return None
    K = keyboard.Key
    ctrl_keys = {K.ctrl, K.ctrl_l, K.ctrl_r}
    alt_keys = {K.alt, K.alt_l, K.alt_r, getattr(K, "alt_gr", K.alt)}
    held = set()

    def letter(key):
        vk = getattr(key, "vk", None)
        if sys.platform == "darwin" and vk in MAC_VK:
            return MAC_VK[vk]
        ch = (getattr(key, "char", None) or "").lower()
        if len(ch) == 1 and "a" <= ch <= "z":
            return ch
        if vk is not None and 65 <= vk <= 90:      # Windows: VK_A..VK_Z
            return chr(vk).lower()
        return None

    def on_press(key):
        if key in ctrl_keys:
            held.add("ctrl")
        elif key in alt_keys:
            held.add("alt")
        elif held >= {"ctrl", "alt"}:
            action = HOTKEYS.get(letter(key))
            if action:
                events[action].set()

    def on_release(key):
        if key in ctrl_keys:
            held.discard("ctrl")
        elif key in alt_keys:
            held.discard("alt")

    try:
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        return listener
    except Exception as e:  # e.g. missing OS permission
        print(f"[!] Global hotkeys unavailable ({e}). Use the preview window keys or Ctrl+C.")
        return None


def open_virtual_camera(w, h, fps, log=print):
    """Returns (camera, None) or (None, error message)."""
    try:
        import pyvirtualcam
        from pyvirtualcam import PixelFormat
        cam = pyvirtualcam.Camera(width=w, height=h, fps=fps, fmt=PixelFormat.BGR)
        log(f"[+] Virtual camera running: {cam.device}  "
            f"(select it as the camera in Zoom/Teams/Meet)")
        return cam, None
    except Exception as e:
        log(f"[!] Virtual camera unavailable: {e}")
        log("    Install OBS Studio, open it once, click 'Start Virtual Camera',\n"
            "    then 'Stop Virtual Camera' and quit OBS. Then try again.")
        return None, str(e)


# ----------------------------------------------------------------- engine ---

class Engine:
    """The whole live pipeline, independent of any UI.

    run() loops on one thread. Other threads control it with command(action)
    (the same actions as the hotkeys) and call(fn), which queues fn(engine) to
    run on the loop thread before the next frame. open_camera() and
    set_output() may be called from any thread; latest_frame() and
    snapshot() are safe to read from any thread."""

    def __init__(self, w=1280, h=720, fps=30, name="Anonymous", title="Operator",
                 duration_scale=1.0, log=print):
        self.w, self.h, self.fps = w, h, fps
        self.name, self.title, self.duration_scale = name, title, duration_scale
        self.log = log
        self.on_action = None             # optional fn(action), called on the loop thread
        self.events = {action: threading.Event() for action in HOTKEYS.values()}
        self._calls = queue.SimpleQueue()
        self._io_lock = threading.Lock()
        self._frame_lock = threading.Lock()
        self._latest = None
        self.measured_fps = 0.0
        self.webcam = None
        self.vcam = None
        self.vcam_device = None
        self.vcam_error = None

        self.vision = Vision()
        self.vision.preload()
        self.pmask = PersonMask(w, h, self.vision)
        self.hacker_filter = HackerFilter(w, h)
        self.matrix_bg = MatrixBackground(w, h)
        self.trace = GlobalTrace(w, h)
        self.hologram = Hologram(w, h)
        self.entrance = Entrance(w, h)
        self.away = AwayScreen(w, h)
        self.filter_on = False
        self.holo_on = False
        self.background = None            # None | "matrix" | "trace"
        self.intro = self.scan = None
        self.intro_start = self.scan_start = 0.0

    # --- control, from any thread -------------------------------------

    def command(self, action):
        self.events[action].set()

    def call(self, fn):
        self._calls.put(fn)

    def stop(self):
        self.events["quit"].set()

    @property
    def running(self):
        return not self.events["quit"].is_set()

    def open_camera(self, index):
        """Switch to webcam `index`. Returns True if it opened."""
        cam = Webcam(index, self.w, self.h, log=self.log)
        with self._io_lock:
            old, self.webcam = self.webcam, cam
        if old is not None:
            old.close()
        return cam.ok

    def set_output(self, on):
        """Start or stop sending to the virtual camera. Returns True if sending."""
        with self._io_lock:
            if on and self.vcam is None:
                self.vcam, self.vcam_error = open_virtual_camera(self.w, self.h, self.fps, self.log)
                self.vcam_device = self.vcam.device if self.vcam is not None else None
            elif not on and self.vcam is not None:
                self.vcam.close()
                self.vcam, self.vcam_device = None, None
                self.log("[+] Virtual camera stopped")
            return self.vcam is not None

    def latest_frame(self):
        with self._frame_lock:
            return self._latest

    def snapshot(self):
        """Current state, for a UI to display."""
        return {
            "filter": self.filter_on,
            "hologram": self.holo_on,
            "background": self.background,
            "away": self.away.state in ("entering", "on"),
            "entrance": self.entrance.state,
            "output": self.vcam is not None,
            "device": self.vcam_device,
            "output_error": self.vcam_error,
            "camera_ok": self.webcam is not None and self.webcam.ok,
            "fps": self.measured_fps,
        }

    def close(self):
        self.vision.close()
        with self._io_lock:
            if self.webcam is not None:
                self.webcam.close()
                self.webcam = None
            if self.vcam is not None:
                self.vcam.close()
                self.vcam = None

    # --- loop thread -------------------------------------------------------

    def _fired(self, action):
        if self.events[action].is_set():
            self.events[action].clear()
            if self.on_action is not None:
                try:
                    self.on_action(action)
                except Exception:
                    pass
            return True
        return False

    def _handle_commands(self, tick):
        while True:
            try:
                fn = self._calls.get_nowait()
            except queue.Empty:
                break
            fn(self)
        if self._fired("replay"):
            self.intro = Intro(self.w, self.h, self.name, self.title, self.duration_scale)
            self.intro_start = tick
        if self._fired("filter"):
            self.filter_on = not self.filter_on
            self.log(f"[+] Hacker filter {'ON' if self.filter_on else 'OFF'}")
        for bg_name in ("matrix", "trace"):      # backgrounds are exclusive
            if self._fired(bg_name):
                self.background = None if self.background == bg_name else bg_name
                self.log(f"[+] Background: {self.background or 'real room'}")
        if self._fired("hologram"):
            self.holo_on = not self.holo_on
            self.log(f"[+] Hologram {'ON' if self.holo_on else 'OFF'}")
        if self._fired("entrance"):
            self.entrance.trigger(tick)
            self.log("[+] Entrance")
        if self._fired("scan"):
            self.scan, self.scan_start = BiometricScan(self.w, self.h, self.name, self.vision), tick
            self.log("[+] Biometric scan")
        if self._fired("away"):
            self.away.toggle(tick)
            self.log(f"[+] Away screen {'ON' if self.away.state == 'entering' else 'OFF'}")

    def step(self, tick):
        """Render one output frame."""
        with self._io_lock:
            webcam = self.webcam
        raw = webcam.get() if webcam is not None else np.zeros((self.h, self.w, 3), np.uint8)
        frame = raw
        if not self.away.covering:       # skip all live processing while hidden
            background, holo_on = self.background, self.holo_on
            need_mask = background is not None or holo_on or self.entrance.state == "playing"
            have_mask = need_mask and self.pmask.update(raw)
            if not need_mask:
                self.pmask.reset()
            bg = None
            if background == "matrix":
                bg = self.matrix_bg.render(tick)
            elif background == "trace":
                bg = self.trace.render(tick)
            if holo_on:
                bg = self.hologram.background(bg if bg is not None else raw)
            if bg is not None and have_mask:
                person = self.hologram.person(raw, tick) if holo_on else raw
                alpha = self.pmask.full()
                if holo_on:
                    alpha = alpha * self.hologram.opacity()
                frame = composite(person, bg, alpha, self.pmask.rim(), CYAN if holo_on else GREEN)
                if holo_on:
                    self.hologram.hud(frame, tick)
            if self.entrance.active:
                if background is not None and bg is not None and have_mask:
                    empty = bg                              # virtual background
                else:
                    empty = None                            # black
                    if holo_on:
                        empty = self.hologram.background(np.zeros_like(raw))
                frame = self.entrance.render(frame, empty,
                                             self.pmask.full() if have_mask else None, tick)
            if self.filter_on:
                frame = self.hacker_filter.apply(frame, tick)
            if self.scan is not None:
                out = self.scan.render(frame, raw, tick - self.scan_start)
                if out is None:
                    self.scan = None
                else:
                    frame = out
            if self.intro is not None:
                out = self.intro.render(tick - self.intro_start, frame)
                if out is None:
                    self.intro = None
                else:
                    frame = out
        return self.away.render(frame, tick)

    def run(self, on_frame=None):
        """Loop until stop() or the quit hotkey. on_frame(frame) is called after
        each frame on this thread; returning False stops the loop."""
        frame_time = 1.0 / self.fps
        next_tick = time.monotonic()
        while self.running:
            tick = time.monotonic()
            self._handle_commands(tick)
            frame = self.step(tick)
            with self._frame_lock:
                self._latest = frame
            with self._io_lock:
                if self.vcam is not None:
                    self.vcam.send(frame)
            if on_frame is not None and on_frame(frame) is False:
                break
            dt = time.monotonic() - tick
            self.measured_fps = 0.9 * self.measured_fps + 0.1 * (1.0 / max(dt, frame_time))
            next_tick = max(next_tick + frame_time, time.monotonic() - frame_time)
            time.sleep(max(0.0, next_tick - time.monotonic()))


# -------------------------------------------------------------------- CLI ---

def parse_args():
    p = argparse.ArgumentParser(description="Hacker-style intro for video calls.")
    p.add_argument("--name", default="Anonymous", help="name shown in the reveal")
    p.add_argument("--title", default="Operator", help="title/subtitle under the name")
    p.add_argument("--camera-index", type=int, default=0, help="real webcam index")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--duration-scale", type=float, default=1.0,
                   help="intro length multiplier (0.5 = twice as fast)")
    p.add_argument("--no-autostart", action="store_true",
                   help="start on the webcam; play the intro only on Ctrl+Alt+H")
    p.add_argument("--filter", action="store_true",
                   help="start with the hacker webcam filter on (toggle: Ctrl+Alt+G)")
    p.add_argument("--matrix-bg", action="store_true",
                   help="start with the matrix-rain background on (toggle: Ctrl+Alt+M)")
    p.add_argument("--trace-bg", action="store_true",
                   help="start with the global-trace map background on (toggle: Ctrl+Alt+T)")
    p.add_argument("--hologram", action="store_true",
                   help="start in hologram mode (toggle: Ctrl+Alt+O)")
    p.add_argument("--entrance", action="store_true",
                   help="start on an empty screen and assemble into view on Ctrl+Alt+E "
                        "(replaces the intro at launch)")
    p.add_argument("--preview", action="store_true",
                   help="also show a local preview window (same letters as the hotkeys)")
    return p.parse_args()


def main():
    args = parse_args()
    engine = Engine(args.width, args.height, args.fps, args.name, args.title, args.duration_scale)
    if not engine.set_output(True) and not args.preview:
        sys.exit(1)
    engine.open_camera(args.camera_index)
    engine.filter_on, engine.holo_on = args.filter, args.hologram
    engine.background = "matrix" if args.matrix_bg else ("trace" if args.trace_bg else None)
    if args.entrance:
        engine.entrance.arm()
    elif not args.no_autostart:
        engine.command("replay")
    hotkeys = start_hotkeys(engine.events)
    print("[+] Hotkeys (Ctrl+Alt+...):\n"
          "      H intro      E entrance        B biometric scan   A away screen\n"
          "      G filter     M matrix bg       T global trace bg  O hologram     Q quit")

    on_frame = None
    if args.preview:
        def on_frame(frame):
            cv2.imshow("hacker intro (preview)", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                return False
            if chr(key) in HOTKEYS:
                engine.command(HOTKEYS[chr(key)])
            return True
    try:
        engine.run(on_frame)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[+] Shutting down.")
        if hotkeys is not None:
            hotkeys.stop()
        engine.close()
        if args.preview:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
