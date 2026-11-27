#!/usr/bin/env bash
# Build "Hacker Cam.app" and a drag-to-Applications .dmg into dist/.
# Usage: packaging/build_macos.sh        (uses .venv/bin/python unless $PYTHON is set)
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-.venv/bin/python}"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' app.py)"
ARCH="$(uname -m)"
APP="dist/Hacker Cam.app"
DMG="dist/HackerCam-${VERSION}-macos-${ARCH}.dmg"

echo "==> Icons"
"$PY" packaging/make_icons.py

echo "==> PyInstaller"
"$PY" -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging/hacker_cam.spec

echo "==> Self-test inside the app bundle"
"$APP/Contents/MacOS/HackerCam" --self-test

echo "==> Ad-hoc code signature"
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

echo "==> Disk image"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -volname "Hacker Cam" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"

echo "==> Done"
du -sh "$APP" "$DMG"
