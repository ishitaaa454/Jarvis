# Jarvis Workspace

Local Windows desktop assistant. Phase 1 delivered the FastAPI + React foundation. **Phase 2** adds offline wake-phrase detection for **“Wake up, Jarvis.”** using Vosk and the Windows microphone.

**Phase 2 does not include** text-to-speech, British male voice, application launching, workspace initialization, Ollama, unrestricted voice commands, email, calendar, news, or advanced cinematic dashboard animations.

## Prerequisites

- Windows 10/11
- Python 3.11+
- Node.js 18+ (20+ recommended)
- PowerShell
- A working microphone (for live wake testing)
- A manually downloaded small English Vosk model (see below)

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

1. Ensure model + microphone permissions are OK
2. Start the app or run `.\scripts\test-wake-listener.ps1`
3. Say clearly: **Wake up, Jarvis.**
4. Expect:
   - Console / activity: wake detected
   - Dashboard banner: **VOICE ACTIVATION CONFIRMED**
   - Assistant state: `LISTENING` → `PROCESSING` → `LISTENING`
5. The assistant must **not** speak or open applications in Phase 2

Accepted variants include punctuation/case differences and `wakeup jarvis` if Vosk merges the tokens.

### Test unrelated phrases

Say “Jarvis”, “Hello Jarvis”, “Wake up”, etc. — the listener must **not** activate.

### Test cooldown

Say the wake phrase twice quickly. The second attempt within `WAKE_COOLDOWN_SECONDS` (default 4) is ignored; wait and try again.

### Development simulation (no mic)

With `ENVIRONMENT=development`:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/voice/test-activation
```

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

- `backend/` — FastAPI app, StateManager, WebSocket, voice service, health API
- `backend/models/` — Vosk model install location (binaries not committed)
- `backend/tools/test_wake_phrase.py` — manual wake-listener utility
- `frontend/` — React dashboard
- `scripts/` — PowerShell helpers including `test-wake-listener.ps1`
- `docs/` — Architecture, development, and phase roadmap

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Development](docs/DEVELOPMENT.md)
- [Phases](docs/PHASES.md)
- [Vosk model setup](backend/models/README.md)

## License

MIT — see [LICENSE](LICENSE).
