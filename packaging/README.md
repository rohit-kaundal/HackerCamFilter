# Building the Hacker Cam installers

| Platform | Output (in `dist/`) | Build on |
|---|---|---|
| macOS | `HackerCam-<version>-macos-<arch>.dmg` (contains `Hacker Cam.app`) | a Mac |
| Windows | `HackerCam-<version>-windows-x64-setup.exe` | Windows |
| Linux | `hacker-cam_<version>_amd64.deb` and `HackerCam-<version>-linux-amd64.tar.gz` | Linux (Debian/Ubuntu) |

PyInstaller can't cross-compile, so each installer is built on its own OS. The GitHub Actions workflow (`.github/workflows/build-installers.yml`) builds all three: run it from the **Actions** tab, or push a tag like `v1.0.0` to also publish them on a GitHub Release.

## Building locally

Install the app's and the build's dependencies into the project's venv first:

```bash
pip install -r requirements.txt -r packaging/requirements-build.txt
```

On Linux, also install the system libraries the build and self-test need. MediaPipe's native library won't load without `libgles2`, and `xvfb` gives the self-test a display on a headless machine:

```bash
sudo apt install libgl1 libegl1 libgles2 libxkbcommon-x11-0 libxcb-cursor0 libfontconfig1 libdbus-1-3 xvfb
```

Then:

```bash
packaging/build_macos.sh          # macOS
packaging/build_linux.sh          # Linux
packaging\build_windows.ps1       # Windows (PowerShell), needs Inno Setup 6: winget install JRSoftware.InnoSetup
```

Each script renders the icons (`make_icons.py`), runs PyInstaller with `hacker_cam.spec`, then runs **`HackerCam --self-test` on the built app**. That loads both MediaPipe models, renders every effect, and imports the virtual-camera, hotkey and Qt Multimedia modules, without touching the webcam or virtual camera. The script stops if anything is missing from the bundle. Only then does it make the installer.

The version comes from `__version__` in `app.py`.

## Code signing

The builds are not signed with a developer certificate. That works, but the first launch shows a warning:

- **macOS:** the app is ad-hoc signed. If you downloaded the DMG, macOS blocks the first launch. Go to System Settings → Privacy & Security → **Open Anyway**, or run `xattr -dr com.apple.quarantine "/Applications/Hacker Cam.app"`. Every rebuild counts as a new app to macOS, so it asks for the camera and Input Monitoring permissions again.
- **Windows:** SmartScreen says "Windows protected your PC". Click **More info → Run anyway**.

To sign properly, set `codesign_identity` in `hacker_cam.spec` to your "Developer ID Application" identity and notarize the DMG with `xcrun notarytool`. On Windows, sign the setup `.exe` with `signtool`.
