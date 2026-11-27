# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Hacker Cam (macOS .app, Windows and Linux folders).
# Build with:  python -m PyInstaller --noconfirm --clean packaging/hacker_cam.spec
import os
import re
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICONS = os.path.join(SPECPATH, "icons")
VERSION = re.search(r'__version__ = "([^"]+)"', open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()).group(1)

datas = [(os.path.join(ROOT, "models"), "models"), (os.path.join(ROOT, "LICENSE"), ".")]
datas += collect_data_files("mediapipe")
# MediaPipe loads its native library from the mediapipe/tasks/c package folder.
binaries = collect_dynamic_libs("mediapipe") + collect_dynamic_libs("pyvirtualcam")
hiddenimports = (collect_submodules("mediapipe.tasks.python")
                 + ["mediapipe.tasks.c"]
                 + collect_submodules("pynput")
                 + collect_submodules("pyvirtualcam")
                 + ["certifi"])           # CA certificates for the optional usage stats

# Big libraries the app never imports. (Not matplotlib: mediapipe imports it.)
excludes = ["tkinter", "IPython", "jax", "jaxlib", "sounddevice",
            "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQuick",
            "PySide6.QtQml", "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization",
            "PySide6.QtPdf", "PySide6.QtDesigner", "PySide6.QtSql", "PySide6.QtTest"]

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == "win32":
    icon = os.path.join(ICONS, "hacker_cam.ico")
elif sys.platform == "darwin":
    icon = os.path.join(ICONS, "hacker_cam.icns")
else:
    icon = None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HackerCam",
    console=False,           # GUI app: no terminal window
    icon=icon,
    target_arch=None,
    codesign_identity=None,  # ad-hoc signed; see packaging/README.md for real signing
)
coll = COLLECT(exe, a.binaries, a.datas, name="HackerCam")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Hacker Cam.app",
        icon=icon,
        bundle_identifier="local.hackercam.app",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "Hacker Cam",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "12.0",
            "LSUIElement": True,     # menu bar app: no Dock icon
            "NSHighResolutionCapable": True,
            "NSCameraUsageDescription":
                "Hacker Cam reads your webcam to add effects and sends the result "
                "to the virtual camera that your call app uses.",
        },
    )
