#!/usr/bin/env python3
"""Hacker-style intro for video calls (Zoom, Teams, Meet, ...).

Renders a "matrix rain -> terminal breach -> ACCESS GRANTED -> name reveal"
animation into a virtual camera, then hands over to your real webcam.
In the call app, pick "OBS Virtual Camera" as your camera.

Hotkeys (global, work while the call app is focused):
    Ctrl+Alt+H  replay the intro
    Ctrl+Alt+Q  quit
"""
import argparse
import random
import sys
import threading
import time

import cv2
import numpy as np

GREEN = (70, 255, 70)          # BGR
DIM_GREEN = (40, 150, 40)
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

def start_hotkeys(replay_evt, quit_evt):
    try:
        from pynput import keyboard
        hk = keyboard.GlobalHotKeys({
            "<ctrl>+<alt>+h": replay_evt.set,
            "<ctrl>+<alt>+q": quit_evt.set,
        })
        hk.start()
        return hk
    except Exception as e:  # missing package or OS permission
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
    p.add_argument("--preview", action="store_true",
                   help="also show a local preview window (keys: h = replay, q = quit)")
    return p.parse_args()


def main():
    args = parse_args()
    w, h, fps = args.width, args.height, args.fps

    vcam = open_virtual_camera(w, h, fps)
    if vcam is None and not args.preview:
        sys.exit(1)

    webcam = Webcam(args.camera_index, w, h)
    replay_evt, quit_evt = threading.Event(), threading.Event()
    hotkeys = start_hotkeys(replay_evt, quit_evt)
    if not args.no_autostart:
        replay_evt.set()
    print("[+] Ctrl+Alt+H = replay intro, Ctrl+Alt+Q (or Ctrl+C) = quit")

    intro, intro_start = None, 0.0
    frame_time = 1.0 / fps
    try:
        while not quit_evt.is_set():
            tick = time.monotonic()
            if replay_evt.is_set():
                replay_evt.clear()
                intro = Intro(w, h, args.name, args.title, args.duration_scale)
                intro_start = tick

            cam_frame = webcam.get()
            frame = cam_frame
            if intro is not None:
                out = intro.render(tick - intro_start, cam_frame)
                if out is None:
                    intro = None
                else:
                    frame = out

            if vcam is not None:
                vcam.send(frame)
            if args.preview:
                cv2.imshow("hacker intro (preview)", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("h"):
                    replay_evt.set()
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
