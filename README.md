# Hacker intro for video calls

Plays a hacker-style intro (matrix rain → terminal "breach" log → ACCESS GRANTED → your name and title) on Zoom, Teams, Meet or any app that lets you choose a camera. When the intro ends, it switches to your real webcam. Hotkeys add live effects during the call: a particle entrance, a hacker filter, a hologram mode, matrix-rain and world-map trace backgrounds, a biometric face scan and an away screen.

It works by sending frames to a **virtual camera** ("OBS Virtual Camera"). The call app sees it as an ordinary webcam.

There are two ways to run it: the **Hacker Cam desktop app** (`app.py`, macOS, Windows and Linux) or the **command-line script** (`hacker_intro.py`). Both have the same effects and hotkeys.

## Install the app

Download the installer for your system (built by GitHub Actions, see [packaging/README.md](packaging/README.md)) or build it yourself:

| System | Installer | Notes |
|---|---|---|
| macOS (Apple Silicon) | `HackerCam-<version>-macos-arm64.dmg` | Open it and drag **Hacker Cam** to Applications. First launch: System Settings → Privacy & Security → **Open Anyway**. Allow **Camera**, and **Input Monitoring** for the hotkeys. |
| Windows 10/11 | `HackerCam-<version>-windows-x64-setup.exe` | If SmartScreen warns, click **More info → Run anyway**. Starts in the system tray. |
| Debian / Ubuntu | `hacker-cam_<version>_amd64.deb` | `sudo apt install ./hacker-cam_*.deb`, then run **Hacker Cam** from the app menu or `hacker-cam`. |
| Other Linux | `HackerCam-<version>-linux-amd64.tar.gz` | Unpack it and run `HackerCam/HackerCam`. Needs the OpenGL ES/EGL libraries and the PulseAudio client library (`libgles2`, `libegl1` and `libpulse0` on Debian/Ubuntu; `libglvnd-gles`, `libglvnd-egl` and `pulseaudio-libs` on Fedora). Most desktops already have them. |

You still need the virtual camera from OBS (macOS/Windows) or v4l2loopback (Linux): see step 1 below. The installers include everything else, and Python isn't needed.

## One-time setup (running from source)

### macOS

1. **Install OBS Studio 30 or later**: https://obsproject.com, or `brew install --cask obs`.
2. Open OBS and click **Start Virtual Camera**. Approve the system extension if macOS asks (System Settings → General → Login Items & Extensions → Camera Extensions). You may need to restart. Then click **Stop Virtual Camera** and quit OBS. OBS doesn't need to be open after this.
3. Install the Python dependencies. pyvirtualcam needs Python 3.10 or later on Apple Silicon:
   ```bash
   uv venv -p python3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt
   # or: python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
4. macOS permissions for your terminal app (Terminal or iTerm), under System Settings → Privacy & Security:
   - **Camera**, so the script can read your real webcam.
   - **Input Monitoring** (or **Accessibility**), so the global hotkeys work.

### Windows

1. Install **OBS Studio 30 or later** from https://obsproject.com. Open it once, click **Start Virtual Camera**, then **Stop Virtual Camera** and quit OBS.
2. Install Python 3.10 or later from https://python.org, then in the project folder:
   ```bat
   py -3 -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

### Linux

1. The virtual camera comes from the `v4l2loopback` kernel module:
   ```bash
   sudo apt install v4l2loopback-dkms          # or your distro's equivalent
   sudo modprobe v4l2loopback devices=1 exclusive_caps=1 card_label="Virtual Camera"
   ```
2. Install the system libraries MediaPipe and Qt need (without `libgles2`, face tracking and background effects won't load), then the Python dependencies:
   ```bash
   sudo apt install libgl1 libegl1 libgles2 libxkbcommon-x11-0 libxcb-cursor0 libpulse0
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
3. Global hotkeys need an X11 session. On Wayland, use the app's buttons instead.

## Desktop app

```bash
.venv/bin/python app.py              # macOS / Linux
.venv\Scripts\python app.py          # Windows
```

Hacker Cam starts as a small **`>_` icon in the menu bar** (macOS) or **system tray** (Windows/Linux). It's green with a red dot while you're live, and grey when you're not sending. Click it (right-click on Windows) for the menu:

- **Status:** for example `● LIVE → OBS Virtual Camera · 30 fps`
- **Send to virtual camera:** on/off
- **Moments:** Play intro, Black screen (waits for the entrance), Entrance, Biometric scan, Away screen
- **Looks:** Hacker filter, Hologram
- **Background ▸** Real room, Matrix rain, Global trace map
- **Webcam ▸** pick your camera
- **Open window ...** and **Quit Hacker Cam**

Each item shows its global hotkey, and ticks update when you use the hotkeys.

**Open window** shows a live preview of exactly what the call sees, plus settings: your name and title, what happens at launch (play intro, black screen or nothing), intro length, global hotkeys on/off, and *Open this window at launch*. Closing the window only hides it, and Hacker Cam keeps running in the menu bar. Quit from the menu or with `Ctrl+Alt+Q`. To open the window straight away, run `app.py --window`. Your settings are remembered between launches.

If your desktop has no tray (some Linux setups), the window opens instead.

## Command-line usage

```bash
.venv/bin/python hacker_intro.py --name "Rohit Kaundal" --title "Lead Engineer"
```

Then in your call app, set the camera to **OBS Virtual Camera**:
- **Zoom:** Settings → Video → Camera
- **Teams:** Settings → Devices → Camera
- **Meet:** ⋮ → Settings → Video

| Hotkey | Action |
|---|---|
| `Ctrl+Alt+H` | Replay the intro |
| `Ctrl+Alt+G` | Toggle the live hacker filter on your webcam (green phosphor, scanlines, static, glitch bursts, REC HUD) |
| `Ctrl+Alt+E` | Entrance (~4 s): you assemble out of particles falling into place, head first, on black, then your room fades in. If the matrix or map background is on, you assemble onto it instead. Filters and hologram apply as usual. Start with `--entrance` to begin on a black `INCOMING SIGNAL ...` screen, then press this when you're ready |
| `Ctrl+Alt+O` | Toggle hologram mode: you become a translucent, flickering cyan projection with rolling scanlines, a glowing outline and a projector glow, with your background dimmed behind you |
| `Ctrl+Alt+T` | Toggle the global-trace background: a dot-matrix world map where a trace hops across 7 cities with IPs and pulses, then `TRACE COMPLETE`/`LOCATED`, then a new route |
| `Ctrl+Alt+M` | Toggle the matrix-rain background: you stay in colour, everything behind you becomes falling code with a green glow around you |
| `Ctrl+Alt+B` | Biometric scan (~5 s): brackets lock onto your face, a laser sweep draws a face mesh, then `BIOMETRIC MATCH · IDENTITY · CLEARANCE LEVEL 5` |
| `Ctrl+Alt+A` | Away screen: your video scrambles into hex and shows `SESSION SUSPENDED` with a running away timer. Press again to come back. Your camera isn't shown while it's on |
| `Ctrl+Alt+Q` or `Ctrl+C` | Quit |

Effects stack: for example, hologram over the world map, matrix background plus hacker filter, or a scan over either background. The two backgrounds (`M` and `T`) replace each other.

Tip: start the script with `--no-autostart`, join the call, then press `Ctrl+Alt+H` when you want the reveal.

The backgrounds, hologram, entrance and biometric scan use MediaPipe (included in `requirements.txt`). The first run downloads two small models (about 4 MB) into `models/`.

### Options

| Flag | Default | Meaning |
|---|---|---|
| `--name` | `Anonymous` | Name in the reveal |
| `--title` | `Operator` | Line under the name |
| `--camera-index` | `0` | Which real webcam to use |
| `--width` / `--height` / `--fps` | 1280 / 720 / 30 | Output format |
| `--duration-scale` | `1.0` | Intro length (0.7 = faster, 1.5 = slower) |
| `--filter` | off | Start with the hacker filter already on |
| `--matrix-bg` | off | Start with the matrix background already on |
| `--trace-bg` | off | Start with the world-map trace background already on |
| `--hologram` | off | Start in hologram mode |
| `--entrance` | off | Start on a black `INCOMING SIGNAL ...` screen; `Ctrl+Alt+E` assembles you into view (replaces the intro at launch) |
| `--no-autostart` | off | Start on the webcam; play the intro only on hotkey |
| `--preview` | off | Show a local preview window (same letters as the hotkeys). Works without OBS, useful for testing |

## Usage stats (optional)

The desktop app can send anonymous usage stats to PostHog: event names such as `app_started` and `effect_used` (with the effect's name), the app version, OS and CPU type, how long the app ran, and a random install ID. It never sends video, images, your name or title, camera names, or anything you type. The code is in `telemetry.py`.

- **Off unless the user agrees.** On first launch the app asks. It can be changed any time under *Options → Share anonymous usage stats*.
- **Off in builds without a key.** Set `POSTHOG_KEY` in `telemetry.py` (and `POSTHOG_HOST` for an EU project) before building. Forks that leave it empty send nothing, and the question never appears. For testing, `HACKERCAM_POSTHOG_KEY` and `HACKERCAM_POSTHOG_HOST` override both.
- **Always off** when `DO_NOT_TRACK=1` or `HACKERCAM_NO_TELEMETRY=1` is set.
- Events don't create person profiles. In the PostHog project settings, also turn on *Discard client IP data*.

The command-line script (`hacker_intro.py`) never sends anything.

## Troubleshooting

- **"Virtual camera unavailable"**: repeat setup step 2. OBS itself must not have its virtual camera running while the script runs.
- **Shows "CAMERA OFFLINE"**: wrong `--camera-index`, or Camera permission is missing. Try `--camera-index 1`. Never point it at OBS Virtual Camera itself.
- **The call app shows a black screen**: make sure the call app has *OBS Virtual Camera* selected, not your real webcam. Some apps need a restart after OBS is installed before the device appears.
- **Hotkeys don't work**: grant Input Monitoring to your terminal, then restart the terminal. Ctrl+C still quits.
- **Matrix background edges flicker or cut into you**: sit facing a light, with some distance from the wall behind you. Segmentation works best with good lighting.
- **Scan doesn't follow your face**: it falls back to a fixed box in the middle. Make sure your face is lit and in frame.
- **Self-view looks mirrored**: that's only the call app's own self-view. Other people see it the right way round.

World map data: [Natural Earth](https://www.naturalearthdata.com/) (public domain), embedded in the script as a small bitmap.

## License

[MIT](LICENSE). Contributions are welcome: open an issue or a pull request.

Third-party parts keep their own licenses: MediaPipe and its models (Apache 2.0), OpenCV (Apache 2.0), PySide6/Qt and pynput (LGPL v3), pyvirtualcam (GPL v2), Natural Earth map data (public domain).

Because the installers bundle pyvirtualcam, each installer as a whole is distributed under the GPL v2. This repository's own code stays MIT, and MIT is compatible with the GPL. In practice: keep the source public (it is) and ship the license texts with the installers.
