# Hacker intro for video calls

Plays a hacker-style intro (matrix rain → terminal "breach" log → ACCESS GRANTED → your name and title) on Zoom, Teams, Meet or any app that lets you choose a camera. When the intro ends, it switches to your real webcam. You can replay it at any time with a hotkey.

It works by sending frames to a **virtual camera** ("OBS Virtual Camera"). The call app sees it as an ordinary webcam.

## One-time setup (macOS)

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

## Usage

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
| `Ctrl+Alt+Q` or `Ctrl+C` | Quit |

Tip: start the script with `--no-autostart`, join the call, then press `Ctrl+Alt+H` when you want the reveal.

### Options

| Flag | Default | Meaning |
|---|---|---|
| `--name` | `Anonymous` | Name in the reveal |
| `--title` | `Operator` | Line under the name |
| `--camera-index` | `0` | Which real webcam to use |
| `--width` / `--height` / `--fps` | 1280 / 720 / 30 | Output format |
| `--duration-scale` | `1.0` | Intro length (0.7 = faster, 1.5 = slower) |
| `--no-autostart` | off | Start on the webcam; play the intro only on hotkey |
| `--preview` | off | Show a local preview window (`h` = replay, `q` = quit). Works without OBS, useful for testing |

## Troubleshooting

- **"Virtual camera unavailable"**: repeat setup step 2. OBS itself must not have its virtual camera running while the script runs.
- **Shows "CAMERA OFFLINE"**: wrong `--camera-index`, or Camera permission is missing. Try `--camera-index 1`. Never point it at OBS Virtual Camera itself.
- **The call app shows a black screen**: make sure the call app has *OBS Virtual Camera* selected, not your real webcam. Some apps need a restart after OBS is installed before the device appears.
- **Hotkeys don't work**: grant Input Monitoring to your terminal, then restart the terminal. Ctrl+C still quits.
- **Self-view looks mirrored**: that's only the call app's own self-view. Other people see it the right way round.
