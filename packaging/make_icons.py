#!/usr/bin/env python3
"""Render the Hacker Cam app icon to packaging/icons/ as .png, .ico and .icns.

Run from anywhere: python packaging/make_icons.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QPen

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


def render(size):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 1024
    # macOS-style rounded square with a dark green gradient.
    rect = QRectF(100 * s, 100 * s, 824 * s, 824 * s)
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0, QColor("#0f1f0f"))
    grad.setColorAt(1, QColor("#030603"))
    p.setBrush(grad)
    p.setPen(QPen(QColor("#46ff46"), 18 * s))
    p.drawRoundedRect(rect, 185 * s, 185 * s)
    # Faint scanlines.
    p.setPen(QPen(QColor(70, 255, 70, 22), max(1.0, 6 * s)))
    y = rect.top() + 40 * s
    while y < rect.bottom() - 40 * s:
        p.drawLine(int(rect.left() + 40 * s), int(y), int(rect.right() - 40 * s), int(y))
        y += 22 * s
    # The prompt.
    font = QFont("Menlo" if sys.platform == "darwin" else "Consolas")
    font.setPixelSize(int(400 * s))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor("#46ff46"))
    p.drawText(rect.adjusted(0, -30 * s, 0, 0), Qt.AlignCenter, ">_")
    # Red REC dot.
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#ff3b3b"))
    p.drawEllipse(QRectF(735 * s, 175 * s, 110 * s, 110 * s))
    p.end()
    return img


def main():
    QGuiApplication(sys.argv)
    os.makedirs(OUT, exist_ok=True)
    big = render(1024)
    outputs = {
        "hacker_cam.png": (big, "PNG"),
        "hacker_cam.ico": (render(256), "ICO"),
        "hacker_cam.icns": (big, "ICNS"),
    }
    for name, (img, fmt) in outputs.items():
        path = os.path.join(OUT, name)
        if not img.save(path, fmt):
            sys.exit(f"could not write {path}")
        print("wrote", path)


if __name__ == "__main__":
    main()
