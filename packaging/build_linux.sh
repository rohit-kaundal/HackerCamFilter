#!/usr/bin/env bash
# Build dist/HackerCam/, a portable .tar.gz and a .deb package (Debian/Ubuntu).
# Usage: packaging/build_linux.sh        (uses .venv/bin/python unless $PYTHON is set)
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-.venv/bin/python}"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' app.py)"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"

echo "==> Icons"
"$PY" packaging/make_icons.py

echo "==> PyInstaller"
"$PY" -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging/hacker_cam.spec

echo "==> Self-test"
# pynput (hotkeys) connects to X11 on import, so a headless machine (CI) needs
# a virtual display: sudo apt install xvfb
if [ -z "${DISPLAY:-}" ] && command -v xvfb-run >/dev/null; then
  xvfb-run -a dist/HackerCam/HackerCam --self-test
else
  dist/HackerCam/HackerCam --self-test
fi

echo "==> Portable archive"
tar -C dist -czf "dist/HackerCam-${VERSION}-linux-${ARCH}.tar.gz" HackerCam

echo "==> Debian package"
PKG="$(mktemp -d)/hacker-cam"
mkdir -p "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" "$PKG/usr/share/applications" "$PKG/usr/share/pixmaps"
cp -R dist/HackerCam "$PKG/opt/hacker-cam"
ln -s /opt/hacker-cam/HackerCam "$PKG/usr/bin/hacker-cam"
cp packaging/icons/hacker_cam.png "$PKG/usr/share/pixmaps/hacker-cam.png"
mkdir -p "$PKG/usr/share/doc/hacker-cam"
cp LICENSE "$PKG/usr/share/doc/hacker-cam/copyright"
cat > "$PKG/usr/share/applications/hacker-cam.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Hacker Cam
Comment=Hacker-style effects for video calls via a virtual camera
Exec=hacker-cam
Icon=hacker-cam
Terminal=false
Categories=AudioVideo;Video;
EOF
cat > "$PKG/DEBIAN/control" <<EOF
Package: hacker-cam
Version: ${VERSION}
Section: video
Priority: optional
Architecture: ${ARCH}
Maintainer: Hacker Cam <hacker-cam@localhost>
Depends: libgl1, libegl1, libgles2, libxkbcommon-x11-0, libxcb-cursor0
Recommends: v4l2loopback-dkms
Description: Hacker-style intro and live effects for video calls
 Sends your webcam with effects (matrix intro, hologram, backgrounds,
 biometric scan, ...) to a virtual camera for Zoom, Teams, Meet and others.
 Needs the v4l2loopback module for the virtual camera.
EOF
dpkg-deb --build --root-owner-group "$PKG" "dist/hacker-cam_${VERSION}_${ARCH}.deb"
rm -rf "$(dirname "$PKG")"

echo "==> Done"
ls -lh dist/*.tar.gz dist/*.deb
