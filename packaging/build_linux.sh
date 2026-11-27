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

# pynput (hotkeys) connects to X11 when imported. PyInstaller imports modules
# while collecting them, and the self-test imports pynput, so on a headless
# machine (CI) both run on a virtual display: sudo apt install xvfb
X=()
if [ -z "${DISPLAY:-}" ] && command -v xvfb-run >/dev/null; then
  X=(xvfb-run -a)
fi

echo "==> PyInstaller"
${X[@]+"${X[@]}"} "$PY" -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging/hacker_cam.spec

echo "==> Check the hotkey backend is bundled"
# PYZ-00.toc lists the Python modules actually packed into the app.
PYZ_TOC="build/hacker_cam/PYZ-00.toc"
for mod in pynput.keyboard._xorg pynput.mouse._xorg Xlib.display; do
  if ! grep -q "'$mod'," "$PYZ_TOC"; then
    echo "ERROR: $mod is missing from the bundle (hotkeys would fail on Linux)." >&2
    exit 1
  fi
  echo "  ok  $mod"
done

echo "==> Self-test"
${X[@]+"${X[@]}"} dist/HackerCam/HackerCam --self-test

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
Depends: libgl1, libegl1, libgles2, libxkbcommon-x11-0, libxcb-cursor0, libpulse0, libx11-6, libxext6, libxrandr2
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
