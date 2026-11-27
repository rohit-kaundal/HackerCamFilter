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
    Ctrl+Alt+A  toggle the "session suspended" away screen
    Ctrl+Alt+Q  quit
"""
import argparse
import os
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

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_URLS = {
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/"
                            "face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
    "selfie_segmenter.tflite": "https://storage.googleapis.com/mediapipe-models/"
                               "image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite",
}


def model_path(name):
    """Path to a MediaPipe model, downloading it on first use."""
    path = os.path.join(MODEL_DIR, name)
    if not os.path.exists(path):
        os.makedirs(MODEL_DIR, exist_ok=True)
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


# ------------------------------------------------------ matrix background ---

class MatrixBackground:
    """Replaces everything behind you with matrix rain and adds a green rim glow."""

    def __init__(self, w, h, vision):
        self.w, self.h = w, h
        self.vision = vision
        self.rain = Rain(w, h, random.Random(), cell=max(10, int(16 * h / 720))).warm()
        self.mask = None
        self.last = time.monotonic()

    def apply(self, frame):
        m = self.vision.segment(frame)
        if m is None:
            return frame
        now = time.monotonic()
        dt, self.last = min(0.1, now - self.last), now
        # Temporal smoothing kills edge flicker; work at half size for speed.
        self.mask = m if self.mask is None else cv2.addWeighted(self.mask, 0.5, m, 0.5, 0)
        m = cv2.GaussianBlur(self.mask, (0, 0), 2)
        rim = np.clip((cv2.GaussianBlur(m, (0, 0), 9) - m) * 2.2, 0, 1)
        rim = cv2.resize(cv2.convertScaleAbs(rim, alpha=255), (self.w, self.h))
        m = cv2.resize(m, (self.w, self.h))

        bg = self.rain.step(dt)
        out = cv2.blendLinear(frame, bg, m, 1 - m)
        glow = cv2.merge([cv2.convertScaleAbs(rim, alpha=GREEN[0] / 255), rim,
                          cv2.convertScaleAbs(rim, alpha=GREEN[2] / 255)])
        return cv2.add(out, glow)


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

    def __init__(self, index, w, h):
        self.w, self.h = w, h
        self.lock = threading.Lock()
        self.frame = None
        self.running = True
        self.standby = self._standby_frame()
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            print(f"[!] Could not open webcam index {index}; showing standby screen.")
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


# ------------------------------------------------------------------- main ---

# Hotkey letter -> action. All are Ctrl+Alt+<letter>.
HOTKEYS = {"h": "replay", "g": "filter", "m": "matrix", "b": "scan", "a": "away", "q": "quit"}
# macOS ANSI virtual key codes: Option+letter types a symbol (Option+H = "˙"),
# so on macOS letters are matched by physical key code instead of character.
MAC_VK = {0: "a", 11: "b", 5: "g", 4: "h", 46: "m", 12: "q"}


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


def open_virtual_camera(w, h, fps):
    try:
        import pyvirtualcam
        from pyvirtualcam import PixelFormat
        cam = pyvirtualcam.Camera(width=w, height=h, fps=fps, fmt=PixelFormat.BGR)
        print(f"[+] Virtual camera running: {cam.device}  "
              f"(select it as the camera in Zoom/Teams/Meet)")
        return cam
    except Exception as e:
        print(f"[!] Virtual camera unavailable: {e}")
        print("    Install OBS Studio, open it once, click 'Start Virtual Camera',\n"
              "    then 'Stop Virtual Camera' and quit OBS. Then rerun this script.")
        return None


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
    p.add_argument("--preview", action="store_true",
                   help="also show a local preview window "
                        "(keys: h intro, g filter, m matrix bg, b scan, a away, q quit)")
    return p.parse_args()


def main():
    args = parse_args()
    w, h, fps = args.width, args.height, args.fps

    vcam = open_virtual_camera(w, h, fps)
    if vcam is None and not args.preview:
        sys.exit(1)

    webcam = Webcam(args.camera_index, w, h)
    events = {action: threading.Event() for action in HOTKEYS.values()}
    hotkeys = start_hotkeys(events)
    if not args.no_autostart:
        events["replay"].set()
    print("[+] Hotkeys (Ctrl+Alt+...):  H intro   G hacker filter   M matrix background\n"
          "                             B biometric scan   A away screen   Q quit")

    def fired(action):
        if events[action].is_set():
            events[action].clear()
            return True
        return False

    vision = Vision()
    vision.preload()
    hacker_filter = HackerFilter(w, h)
    matrix_bg = MatrixBackground(w, h, vision)
    away = AwayScreen(w, h)
    filter_on, matrix_on = args.filter, args.matrix_bg
    intro, intro_start = None, 0.0
    scan, scan_start = None, 0.0
    frame_time = 1.0 / fps
    try:
        while not events["quit"].is_set():
            tick = time.monotonic()
            if fired("replay"):
                intro = Intro(w, h, args.name, args.title, args.duration_scale)
                intro_start = tick
            if fired("filter"):
                filter_on = not filter_on
                print(f"[+] Hacker filter {'ON' if filter_on else 'OFF'}")
            if fired("matrix"):
                matrix_on = not matrix_on
                print(f"[+] Matrix background {'ON' if matrix_on else 'OFF'}")
            if fired("scan"):
                scan, scan_start = BiometricScan(w, h, args.name, vision), tick
                print("[+] Biometric scan")
            if fired("away"):
                away.toggle(tick)
                print(f"[+] Away screen {'ON' if away.state == 'entering' else 'OFF'}")

            raw = webcam.get()
            frame = raw
            if not away.covering:       # skip all live processing while hidden
                if matrix_on:
                    frame = matrix_bg.apply(frame)
                if filter_on:
                    frame = hacker_filter.apply(frame, tick)
                if scan is not None:
                    out = scan.render(frame, raw, tick - scan_start)
                    if out is None:
                        scan = None
                    else:
                        frame = out
                if intro is not None:
                    out = intro.render(tick - intro_start, frame)
                    if out is None:
                        intro = None
                    else:
                        frame = out
            frame = away.render(frame, tick)

            if vcam is not None:
                vcam.send(frame)
            if args.preview:
                cv2.imshow("hacker intro (preview)", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if chr(key) in HOTKEYS:
                    events[HOTKEYS[chr(key)]].set()
            if vcam is not None:
                vcam.sleep_until_next_frame()
            else:
                time.sleep(max(0.0, frame_time - (time.monotonic() - tick)))
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[+] Shutting down.")
        if hotkeys is not None:
            hotkeys.stop()
        webcam.close()
        if vcam is not None:
            vcam.close()
        if args.preview:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
