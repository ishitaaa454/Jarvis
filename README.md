# Jarvis Workspace

Local Windows desktop assistant. Phase 1 delivered the FastAPI + React foundation. Phase 2 added offline wake-phrase detection. **Phase 3** adds offline British male text-to-speech (Piper) and the fixed welcome sequence after “Wake up, Jarvis.”

**Phase 3 does not include** application launching, email, calendar, news, Ollama, unrestricted voice commands, Windows startup packaging, or advanced cinematic dashboard animations.

## Prerequisites

- Windows 10/11
- Python 3.11+
- Node.js 18+ (20+ recommended)
- PowerShell
- A working microphone (for live wake testing)
- Speakers or headphones (for welcome speech)
- A manually downloaded small English Vosk model (see below)
- Piper for Windows + `en_GB-alan-medium` voice files (see Phase 3)

## Setup (PowerShell)

Run these from the repository root unless noted.

### 1. Check Python and Node versions

```powershell
python --version
node --version
npm --version
```

### 2. Create the Python virtual environment

```powershell
cd backend
python -m venv .venv
```

### 3. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If activation is blocked by execution policy:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 4. Install backend dependencies

```powershell
pip install -r requirements-dev.txt
```

Phase 2 adds `vosk`, `sounddevice`, and `numpy`. PortAudio is bundled with the `sounddevice` wheels on Windows in typical installs.

### 5. Install the Vosk model (required for listening)

The backend does **not** auto-download models.

1. Download a small English model from https://alphacephei.com/vosk/models  
   (recommended: `vosk-model-small-en-us-0.15`)
2. Extract to:

```text
backend/models/vosk-model-small-en-us/
```

3. Confirm markers exist:

```powershell
Test-Path .\models\vosk-model-small-en-us\am
Test-Path .\models\vosk-model-small-en-us\conf
Test-Path .\models\vosk-model-small-en-us\graph
```

Full instructions: [backend/models/README.md](backend/models/README.md).

### 6. Install frontend dependencies

```powershell
cd ..\frontend
npm install
```

### 7. Create local `.env` files from examples

```powershell
cd ..\backend
Copy-Item .env.example .env

cd ..\frontend
Copy-Item .env.example .env
```

Important Phase 2 keys in `backend/.env`:

```env
VOICE_ENABLED=true
VOICE_START_AUTOMATICALLY=true
WAKE_PHRASE=Wake up Jarvis
VOSK_MODEL_PATH=models/vosk-model-small-en-us
VOICE_DEVICE_ID=
WAKE_CONFIDENCE_THRESHOLD=0.65
WAKE_COOLDOWN_SECONDS=4
ENVIRONMENT=development
```

### 8. Start both using the development script

```powershell
cd scripts
.\start-development.ps1
```

Or start separately with `.\start-backend.ps1` and `.\start-frontend.ps1`.

### 9. Open the application

- Dashboard: http://localhost:5173
- Health API: http://127.0.0.1:8765/api/health
- Voice status: http://127.0.0.1:8765/api/voice/status
- WebSocket: ws://127.0.0.1:8765/ws

## Phase 2 — wake phrase

### List microphones

```powershell
cd scripts
.\test-wake-listener.ps1 -ListDevices
```

Or:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python tools\test_wake_phrase.py --list-devices
```

### Select a microphone

- Dashboard **Settings → Wake phrase** dropdown, or
- Set `VOICE_DEVICE_ID` in `backend/.env`, or
- `PUT /api/voice/device` with `{ "device_id": 1 }`

Device IDs can change after Windows restarts; prefer re-listing devices.

### Start / stop the listener

- Home **Wake Listener** panel buttons, or Settings Start/Stop
- `POST /api/voice/start` and `POST /api/voice/stop`

### Test “Wake up, Jarvis.”

1. Ensure Vosk model + microphone permissions are OK
2. Optionally install Piper + `en_GB-alan-medium` (Phase 3) for spoken welcome
3. Start the app or run `.\scripts\test-wake-listener.ps1`
4. Say clearly: **Wake up, Jarvis.**
5. Expect:
   - Dashboard banner: **VOICE ACTIVATION CONFIRMED**
   - Assistant state: `LISTENING` → `PROCESSING` → `SPEAKING` → `LISTENING` (with Piper)
   - Three welcome sentences spoken in order (with Piper)
6. Applications are **not** opened in Phase 3

Accepted wake variants include punctuation/case differences and `wakeup jarvis` if Vosk merges the tokens.

### Test unrelated phrases

Say “Jarvis”, “Hello Jarvis”, “Wake up”, etc. — the listener must **not** activate.

### Test cooldown

Say the wake phrase twice quickly. The second attempt within `WAKE_COOLDOWN_SECONDS` (default 4) is ignored; wait and try again.

### Development simulation (no mic)

With `ENVIRONMENT=development`:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/voice/test-activation
# Or full welcome via coordinator:
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/tts/test-welcome
```

## Phase 3 — British male TTS (Piper)

### Install Piper on Windows

See [backend/voices/README.md](backend/voices/README.md).

1. Download `piper_windows_amd64.zip` from https://github.com/rhasspy/piper/releases
2. Extract (keep `piper.exe` + DLLs + `espeak-ng-data` together)
3. Set `PIPER_EXECUTABLE_PATH` in `backend/.env`

### Install `en_GB-alan-medium`

Place both files under:

```text
backend/voices/en_GB-alan-medium/en_GB-alan-medium.onnx
backend/voices/en_GB-alan-medium/en_GB-alan-medium.onnx.json
```

### List / select output devices

```powershell
.\scripts\test-tts.ps1 -ListDevices
```

Or Settings → Speech output. Device IDs can change after reboot.

### Test welcome sequence

```powershell
.\scripts\test-tts.ps1
.\scripts\test-tts.ps1 -DeviceId 4
.\scripts\test-tts.ps1 -Line 1
```

Dashboard: Home **Speech Engine** → Test welcome / Cancel.

### Expected spoken lines (exact)

1. Welcome back, Ishita. Initializing your workspace.
2. All systems are online.
3. Opening your workspace now.

### TTS troubleshooting

| Issue | What to do |
| --- | --- |
| Piper missing | Install Windows zip; set `PIPER_EXECUTABLE_PATH` |
| Model missing | Place `.onnx` + `.onnx.json` under `backend/voices/...` |
| Silent playback | Select correct output device; check Windows volume / exclusive mode |
| Mic not resuming | Use Cancel or Retry; check logs for resume errors |
| Wrong speakers | Change device in Settings or `TTS_OUTPUT_DEVICE_ID` |

Synthesis is local and offline — no API key and no paid cloud TTS.

## Windows microphone troubleshooting

### Permissions (Windows 10 / 11)

1. **Settings → Privacy & security → Microphone**
2. Enable microphone access for the device
3. Allow desktop apps to access the microphone
4. Restart the backend after changing permissions

### Exclusive access

Close Zoom, Teams, Discord, or other apps that may lock the mic. Then `POST /api/voice/start` or use Retry in Settings.

### Invalid sample rates

Jarvis requests 16 kHz mono PCM. If the device rejects 16 kHz, it opens at the native rate and resamples. Persistent failures appear as voice `ERROR` with a clear message — the rest of the API still runs.

### Missing model

If `VOSK_MODEL_PATH` is missing/invalid:

- FastAPI still starts
- Health and dashboard still work
- Voice status is `MODEL_MISSING`
- Install the model per `backend/models/README.md` and restart or Retry

### Offline confirmation

All recognition runs locally through Vosk. No cloud speech API and no API key are used for wake detection.

## Tests and build

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q

cd ..\frontend
npm run typecheck
npm run build
```

## Project layout

- `backend/` — FastAPI app, StateManager, WebSocket, voice + TTS services
- `backend/models/` — Vosk model install location (binaries not committed)
- `backend/voices/` — Piper voice install location (binaries not committed)
- `backend/tools/` — `test_wake_phrase.py`, `test_tts.py`
- `frontend/` — React dashboard
- `scripts/` — PowerShell helpers including `test-wake-listener.ps1`, `test-tts.ps1`
- `docs/` — Architecture, development, and phase roadmap

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Development](docs/DEVELOPMENT.md)
- [Phases](docs/PHASES.md)
- [Vosk model setup](backend/models/README.md)
- [Piper voice setup](backend/voices/README.md)

## License

MIT — see [LICENSE](LICENSE).
