#!/usr/bin/env python3
"""Render real Hacker Cam frames for the website into website/assets/.

Uses the app's own effect code, so the screenshots are exactly what a call
sees. Only effects that don't need a person are rendered (no stock faces).

    .venv/bin/python website/scripts/render_assets.py
"""
import os
import sys

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "website", "assets")
sys.path.insert(0, ROOT)
import hacker_intro as hi  # noqa: E402

W, H = 1280, 720
NAME, TITLE = "Your Name", "Security Engineer"


def save(name, frame):
    path = os.path.join(OUT, name)
    cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
    print(f"wrote {path} ({os.path.getsize(path) // 1024} KB)")


def intro_frames():
    intro = hi.Intro(W, H, NAME, TITLE, seed=7)
    cam = np.zeros((H, W, 3), np.uint8)
    wanted = {2.2: "intro-rain.jpg", 5.4: "intro-terminal.jpg",
              6.5: "intro-granted.jpg", 9.4: "intro-name.jpg"}
    t = 0.0
    while wanted:
        frame = intro.render(t, cam)
        for at in [a for a in wanted if t >= a]:
            save(wanted.pop(at), frame)
        t += 1 / 30


def away_frame():
    away = hi.AwayScreen(W, H)
    away.toggle(0.0)
    frame = None
    for i in range(60):                     # through the transition
        frame = away.render(np.zeros((H, W, 3), np.uint8), 0.1 + i / 30)
    away.since = 0.1 - 187                  # show a believable timer
    save("away.jpg", away.render(frame, 2.2))


def trace_frames():
    trace = hi.GlobalTrace(W, H)
    trace.rng.seed(11)
    t0, frame = 100.0, None
    for i in range(int(5.2 * 30)):
        frame = trace.render(t0 + i / 30)
    save("trace-tracing.jpg", frame)
    for i in range(int(5.2 * 30), int(9.3 * 30)):
        frame = trace.render(t0 + i / 30)
    save("trace-located.jpg", frame)


def matrix_frame():
    import time
    bg = hi.MatrixBackground(W, H)
    start, frame = time.monotonic(), None   # it times itself from monotonic()
    for i in range(45):
        frame = bg.render(start + (i + 1) / 30)
    save("matrix.jpg", frame)


def social_card():
    """1200x630 preview image for link sharing."""
    intro = hi.Intro(W, H, NAME, TITLE, seed=7)
    cam = np.zeros((H, W, 3), np.uint8)
    t, frame = 0.0, None
    while t < 6.5:
        frame = intro.render(t, cam)
        t += 1 / 30
    card = cv2.resize(frame, (1200, 675))[22:652]
    save("social-card.jpg", card)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    intro_frames()
    away_frame()
    trace_frames()
    matrix_frame()
    social_card()
