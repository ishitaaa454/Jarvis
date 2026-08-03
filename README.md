# Jarvis Workspace — Double-Clap Detector

Local Windows microphone listener that detects a reliable **double clap**.  
This step does **not** include voice recognition, wake words, TTS, a dashboard, or cloud APIs.

## Requirements

- Windows 10/11
- Python 3.11 or newer
- A working default microphone (and Windows microphone permission granted)

## Setup (Windows PowerShell)

Open PowerShell, then run these commands from the project folder:

```powershell
cd "C:\Users\Ishita Joshi\Desktop\Projects\Jarvis\jarvis-workspace"
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If activation is blocked by execution policy, run this once for your user account, then activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the program:

```powershell
python main.py
```

Stop cleanly with `Ctrl+C`.

## Expected console output

```
Jarvis listener started.
Calibrating microphone...
Calibration complete.
  Background peak (median): 0.0xxxx
  Clap threshold:           0.0xxxx
Listening for double claps...
First clap detected.
Second clap detected.
DOUBLE CLAP CONFIRMED.
Cooldown active...
```

After a confirmed double clap, the detector waits 3 seconds (cooldown) before accepting new claps.

## Adjusting clap sensitivity

Edit `config.py`:

| Setting | Effect |
|---|---|
| `THRESHOLD_MULTIPLIER` | **Main sensitivity control.** Lower = more sensitive; higher = stricter. Default `6.0`. |
| `MIN_THRESHOLD` | Absolute minimum peak for a clap (default `0.22`). Raise if idle noise still triggers. |
| `MIN_CREST_FACTOR` / `MIN_HF_RATIO` | Require impulsive, sharp sounds (rejects soft clicks / speech). |
| `MIN_RISE_RATIO` | How sharp a rise above recent quiet level must be. |
| `MIN_CLAP_INTERVAL` / `MAX_CLAP_INTERVAL` | Timing window between the two claps (default 0.25–1.5 s). |
| `MAX_CLAP_DURATION` | Maximum length of a single clap peak. |
| `COOLDOWN_DURATION` | Seconds to ignore new claps after a confirmed double clap. |

Tips:

- False triggers without clapping → raise `MIN_THRESHOLD` (try `0.28`–`0.35`) or `THRESHOLD_MULTIPLIER` (try `8`).
- Real claps not detected → lower `MIN_THRESHOLD` / `THRESHOLD_MULTIPLIER` slightly, clap closer to the mic, stay quiet during calibration.
- Same clap counted twice → increase `CLAP_REFRACTORY` slightly.

## Project structure

```
jarvis-workspace/
├── main.py
├── clap_detector.py
├── config.py
├── requirements.txt
├── logs/
│   ├── .gitkeep
│   └── jarvis.log   (created at runtime)
└── README.md
```

## Error handling

The program exits with a clear message if:

- No microphone is found
- Microphone permission is denied
- The audio stream fails to open
- `numpy` or `sounddevice` is not installed

Events and errors are appended to `logs/jarvis.log`.
