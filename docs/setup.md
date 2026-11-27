---
layout: page
title: "Setup guide · Hacker Cam"
heading: Setup guide
eyebrow: Five minutes, once
description: "Install Hacker Cam, turn on the virtual camera and pick it in Zoom, Teams or Meet. Setup for macOS, Windows and Linux."
lede: "Install the app, switch on the virtual camera once, then pick it in your call app. After that, every effect is one click or one keystroke away."
permalink: /setup/
---

## 1. Install Hacker Cam

Download the installer for your system from the [latest release]({{ site.github_url }}/releases/latest).

| System | File | Notes |
|---|---|---|
| macOS (Apple Silicon) | `HackerCam-<version>-macos-arm64.dmg` | Open it and drag **Hacker Cam** to Applications. First launch: System Settings → Privacy & Security → **Open Anyway**. Allow **Camera**, and **Input Monitoring** for the hotkeys. |
| Windows 10/11 | `HackerCam-<version>-windows-x64-setup.exe` | If SmartScreen warns, click **More info → Run anyway**. Starts in the system tray. |
| Debian / Ubuntu | `hacker-cam_<version>_amd64.deb` | `sudo apt install ./hacker-cam_*.deb`, then run **Hacker Cam** from the app menu. |
| Other Linux | `HackerCam-<version>-linux-amd64.tar.gz` | Unpack it and run `HackerCam/HackerCam`. Needs the OpenGL ES/EGL libraries and the PulseAudio client library (`libgles2`, `libegl1` and `libpulse0` on Debian/Ubuntu; `libglvnd-gles`, `libglvnd-egl` and `pulseaudio-libs` on Fedora). Most desktops already have them. |

The installers include everything. You don't need Python.

## 2. Turn on the virtual camera (once)

Operating systems don't let apps create a camera on their own, so Hacker Cam uses a free, trusted driver.

### macOS and Windows

1. Install **OBS Studio 30 or later** from [obsproject.com](https://obsproject.com) (on a Mac you can also run `brew install --cask obs`).
2. Open OBS and click **Start Virtual Camera**. On macOS, approve the system extension if asked (System Settings → General → Login Items & Extensions → Camera Extensions). You may need to restart.
3. Click **Stop Virtual Camera** and quit OBS. You don't need to open OBS again.

### Linux

```bash
sudo apt install v4l2loopback-dkms          # or your distro's equivalent
sudo modprobe v4l2loopback devices=1 exclusive_caps=1 card_label="Virtual Camera"
```

Global hotkeys need an X11 session. On Wayland, use the tray menu instead.

## 3. Pick it in your call app

Choose **OBS Virtual Camera** as your camera:

- **Zoom:** Settings → Video → Camera
- **Microsoft Teams:** Settings → Devices → Camera
- **Google Meet:** ⋮ → Settings → Video

Hacker Cam lives in the **menu bar** (macOS) or **system tray** (Windows, Linux) as a `>_` icon. It turns green with a red dot while you're live. Its menu has every effect, your webcam choice and **Open window**, which shows a live preview plus settings such as your name and title.

## Hotkeys

They work while your call app is in front.

| Hotkey | Effect |
|---|---|
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>H</kbd> | Play the hacker intro |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>E</kbd> | Particle entrance |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>B</kbd> | Biometric scan |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>A</kbd> | Away screen on/off |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>G</kbd> | Hacker filter on/off |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>O</kbd> | Hologram on/off |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>M</kbd> | Matrix background on/off |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>T</kbd> | Global trace background on/off |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Q</kbd> | Quit |

On a Mac, <kbd>Ctrl</kbd> is <kbd>⌃</kbd> and <kbd>Alt</kbd> is <kbd>⌥</kbd>.

## Troubleshooting

- **"Virtual camera unavailable":** repeat step 2. OBS itself must not be running its virtual camera at the same time.
- **The call shows a black screen:** make sure the call app has *OBS Virtual Camera* selected and Hacker Cam is running. Some apps need a restart after OBS is installed before the camera appears.
- **"CAMERA OFFLINE":** pick your real webcam in the tray menu under **Webcam**, never OBS Virtual Camera itself. On macOS, check the Camera permission.
- **Hotkeys don't work:** on macOS, allow Input Monitoring for Hacker Cam, then restart it.
- **Background edges flicker:** sit facing a light, with some distance from the wall behind you.
- **Your self-view looks mirrored:** that's only your call app's self-view. Others see you the right way round.

Still stuck? [Open an issue]({{ site.github_url }}/issues).
