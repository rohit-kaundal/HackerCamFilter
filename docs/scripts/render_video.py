#!/usr/bin/env python3
"""Render a short promo video of Hacker Cam using the app's own effect code.

    .venv/bin/python docs/scripts/render_video.py --name "Your Name" \
        --title "Builder" --out ~/Desktop/hacker-cam-promo.mp4

Needs ffmpeg with libx264 on PATH (H.264 + yuv420p plays everywhere,
including WhatsApp and LinkedIn). No webcam or person is used.
"""
import argparse
import os
import subprocess
import sys

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
import hacker_intro as hi  # noqa: E402

W, H, FPS = 1280, 720, 30
FONT = cv2.FONT_HERSHEY_DUPLEX
MONO = cv2.FONT_HERSHEY_PLAIN
URL = "rohit-kaundal.github.io/HackerCamFilter"


def card(lines, rain=None):
    """Dark card with centred lines [(text, scale, color, glow)]."""
    frame = rain.copy() // 4 if rain is not None else np.zeros((H, W, 3), np.uint8)
    n = len(lines)
    for i, (text, scale, color, glow) in enumerate(lines):
        cy = int(H / 2 + (i - (n - 1) / 2) * 90)
        hi.put_centered(frame, text, cy, FONT, scale, 2 if scale < 1.6 else 3, color, glow)
    return frame


def glitch_cut(a, b, frames, rng):
    """Short glitchy crossfade from frame a to frame b."""
    mask = hi.make_scanline_mask(W, H)
    for i in range(frames):
        alpha = (i + 1) / frames
        out = hi.glitch(hi.crossfade(a, b, alpha), 0.8 * (1 - alpha), rng)
        yield hi.scanlines(out, mask)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="Your Name")
    ap.add_argument("--title", default="Security Engineer")
    ap.add_argument("--out", default=os.path.expanduser("~/Desktop/hacker-cam-promo.mp4"))
    args = ap.parse_args()

    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
         "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", args.out],
        stdin=subprocess.PIPE)
    write = lambda f: ff.stdin.write(np.ascontiguousarray(f, np.uint8).tobytes())  # noqa: E731
    import random
    rng = random.Random(3)

    # 1. The intro, ending on a "your webcam" card instead of a real camera.
    webcam = card([("...then your normal webcam.", 1.4, hi.HEAD_COLOR, False),
                   ("(Zoom / Teams / Meet see it as just another camera)", 0.8, hi.DIM_GREEN, False)])
    intro = hi.Intro(W, H, args.name, args.title, seed=7)
    t, last = 0.0, None
    while (frame := intro.render(t, webcam)) is not None:
        write(frame)
        last = frame
        t += 1 / FPS
    for _ in range(int(1.8 * FPS)):
        write(webcam)
    last = webcam

    # 2. Bonus effects: global trace, then the away screen.
    trace = hi.GlobalTrace(W, H)
    trace.rng.seed(11)
    t0 = 100.0
    first = trace.render(t0)
    for f in glitch_cut(last, first, 10, rng):
        write(f)
    for i in range(1, int(9.5 * FPS)):
        last = trace.render(t0 + i / FPS)
        write(last)

    away = hi.AwayScreen(W, H)
    away.toggle(0.0)
    away.since = -187                       # a believable "away for" timer
    for i in range(int(4.5 * FPS)):
        last = away.render(last if i < 30 else np.zeros((H, W, 3), np.uint8), i / FPS)
        write(last)

    # 3. End card over matrix rain.
    bg = hi.MatrixBackground(W, H)
    for i in range(int(4.5 * FPS)):
        rain = bg.render(bg.last + 1 / FPS)
        end = card([("HACKER CAM", 2.4, hi.GREEN, True),
                    ("Free & open source  |  Mac, Windows, Linux", 0.9, hi.HEAD_COLOR, False),
                    (URL, 1.0, hi.GREEN, False)], rain)
        if i < 10:
            end = list(glitch_cut(last, end, 10, rng))[i]
        write(end)

    ff.stdin.close()
    ff.wait()
    print(f"wrote {args.out} ({os.path.getsize(args.out) // 1024} KB)")


if __name__ == "__main__":
    main()
