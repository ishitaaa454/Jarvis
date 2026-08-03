# Jarvis Workspace — Double Clap + Offline Wake Phrase

Local Windows assistant step 2:

1. Detect a **double clap** on the default microphone  
2. Listen offline for **“Wake up, Jarvis”** with **Vosk**  
3. Return to clap detection  

This step does **not** include TTS, a dashboard, app launching, or cloud APIs.

## Requirements

- Windows 10/11
- Python 3.11 or newer
- Working default microphone
- Vosk model `vosk-model-small-en-us-0.15` extracted under `models/`

## Setup (Windows PowerShell)

```powershell
cd "C:\Users\Ishita Joshi\Desktop\Projects\Jarvis\jarvis-workspace"
```

Activate the existing virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies (includes Vosk):

```powershell
pip install -r requirements.txt
```

### Download and place the Vosk model

1. Download: https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip  
2. Extract into `models\` so you have:

```text
jarvis-workspace\models\vosk-model-small-en-us-0.15\am\
jarvis-workspace\models\vosk-model-small-en-us-0.15\conf\
jarvis-workspace\models\vosk-model-small-en-us-0.15\graph\
```

PowerShell example (zip already in `models\`):

```powershell
cd "C:\Users\Ishita Joshi\Desktop\Projects\Jarvis\jarvis-workspace\models"
Expand-Archive -Path ".\vosk-model-small-en-us-0.15.zip" -DestinationPath "." -Force
Test-Path ".\vosk-model-small-en-us-0.15\am"
```

`config.py` setting:

```python
VOSK_MODEL_PATH = "models/vosk-model-small-en-us-0.15"
```

More detail: `models/README.md`.

### Run

```powershell
cd "C:\Users\Ishita Joshi\Desktop\Projects\Jarvis\jarvis-workspace"
python main.py
```

Stop with `Ctrl+C`.

## Testing

### Successful wake phrase

1. Double clap  
2. Within 7 seconds say: **Wake up, Jarvis** (also try “Wake up Jarvis” / “Wakeup Jarvis”)

Expected:

```text
Jarvis listener started.
Calibrating microphone...
Calibration complete.
Listening for double clap...
First clap detected.
Second clap detected.
DOUBLE CLAP CONFIRMED.
Listening for wake phrase...
Heard: wake up jarvis
WAKE PHRASE CONFIRMED.
Jarvis activated.
Returning to clap detection.
```

### Incorrect phrase

After the double clap, say **Hello Jarvis** or **Open Jarvis** or only **Wake up**:

```text
DOUBLE CLAP CONFIRMED.
Listening for wake phrase...
Heard: hello jarvis
Wake phrase not matched.
Returning to clap detection.
```

### Timeout

After the double clap, stay silent for 7 seconds:

```text
DOUBLE CLAP CONFIRMED.
Listening for wake phrase...
Wake phrase timeout.
Returning to clap detection.
```

## Microphone handoff (important)

Clap detection and speech recognition **never** share the mic at the same time:

1. Double clap confirmed  
2. Clap `InputStream` is **stopped and closed**  
3. ~300 ms delay (`WAKE_START_DELAY`)  
4. Wake listener opens its own stream, listens ≤ 7 s, then **closes** it  
5. Clap detector **re-opens** its stream and resumes  

### Troubleshooting mic conflicts

- “Device busy” / stream errors → only one `python main.py` should be running; close other apps using the mic  
- Restart the program after a crash so streams are released  
- Allow mic access: Windows Settings → Privacy & security → Microphone  
- Confirm the default input device in Windows sound settings  

## Configuration (`config.py`)

| Setting | Purpose |
|---|---|
| `VOSK_MODEL_PATH` | Extracted Vosk model folder |
| `WAKE_PHRASE` | Canonical phrase (`wake up jarvis`) |
| `WAKE_LISTEN_TIMEOUT` | Seconds to wait for speech (default `7.0`) |
| `WAKE_START_DELAY` | Delay after clap before speech mic (default `0.3`) |
| `SPEECH_SAMPLE_RATE` | Vosk sample rate (`16000`) |
| Clap settings | Same as before (`MIN_THRESHOLD`, etc.) |

## Project structure

```text
jarvis-workspace/
├── main.py
├── clap_detector.py
├── wake_word_listener.py
├── config.py
├── requirements.txt
├── models/
│   ├── README.md
│   └── vosk-model-small-en-us-0.15/   (you download this)
├── logs/
│   └── .gitkeep
└── README.md
```

## Error handling

Clear errors for:

- Missing `numpy` / `sounddevice` / `vosk`
- Missing or invalid Vosk model path
- Microphone permission / stream failures
- Empty or unrecognized speech (timeout / not matched)

Events are appended to `logs/jarvis.log`.
