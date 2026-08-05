# Jarvis Workspace

Local Windows desktop assistant. Phase 1 delivered the FastAPI + React foundation. Phase 2 added offline wake-phrase detection. Phase 3 added offline British male text-to-speech (Piper). **Phase 4** opens and restores the configured Windows workspace applications after the welcome sequence.

**Phase 4 does not include** advanced cinematic dashboard graphs, live window previews, calendar, email unread counts, news summarisation, Ollama, unrestricted voice commands, or Windows startup packaging.

## Prerequisites

- Windows 10/11
- Python 3.11+
- Node.js 18+ (20+ recommended)
- PowerShell
- A working microphone (for live wake testing)
- Speakers or headphones (for welcome speech)
- A manually downloaded small English Vosk model (see below)
- Piper for Windows + `en_GB-alan-medium` voice files (see Phase 3)
- Optional: VS Code, Chrome, Teams, WhatsApp, Spotify installed for live workspace tests

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

Phase 2 adds `vosk`, `sounddevice`, and `numpy`. Phase 4 adds `pywin32` (Windows only). PortAudio is bundled with the `sounddevice` wheels on Windows in typical installs.

If `import win32gui` fails after install, run:

```powershell
python -m pywin32_postinstall -install
```

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

Important Phase 4 keys in `backend/.env`:

```env
WORKSPACE_ENABLED=true
WORKSPACE_START_AFTER_WELCOME=true
WORKSPACE_CONFIG_PATH=config/applications.json
GMAIL_URL=https://mail.google.com/
NEWS_URL=https://news.google.com/
VSCODE_EXECUTABLE_PATH=
CHROME_EXECUTABLE_PATH=
TEAMS_EXECUTABLE_PATH=
WHATSAPP_EXECUTABLE_PATH=
SPOTIFY_EXECUTABLE_PATH=
```

Application definitions (no machine-specific paths in the committed defaults):

```text
backend/config/applications.json
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
- Workspace status: http://127.0.0.1:8765/api/workspace/status
- WebSocket: ws://127.0.0.1:8765/ws

## Phase 4 — Windows workspace launching

### How executable discovery works

For each approved application, Jarvis resolves launch targets in this order:

1. Explicit path from `.env` / config override
2. Approved command on `PATH` (for example `code.cmd`)
3. Windows App Paths when practical
4. Common install folders via `LOCALAPPDATA`, `PROGRAMFILES`, `PROGRAMFILES(X86)`

Discovery does not execute applications and does not scan the whole drive.

### List windows

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python tools\list_windows.py
python tools\list_windows.py --include-titles
```

Titles are omitted by default (privacy).

### List Start Apps

```powershell
python tools\list_start_apps.py
python tools\list_start_apps.py --filter teams
python tools\list_start_apps.py --filter whatsapp
```

### Test one application

```powershell
cd scripts
.\test-workspace.ps1 -AppId vscode
.\test-workspace.ps1 -AppId chrome
.\test-workspace.ps1 -AppId gmail
```

### Test the full workspace

```powershell
.\test-workspace.ps1
.\test-workspace.ps1 -NoFocus
.\test-workspace.ps1 -List
.\test-workspace.ps1 -Status
```

Ctrl+C cancels remaining launches without killing already-opened apps.

### Dashboard controls

- Home **Workspace** panel: start, cancel, refresh, live per-app progress
- Applications page: Open / Focus / status cards for configured apps
- Settings: enable/order/URL visibility (safe edits only; no arbitrary commands)
- System page: workspace controller / registry / process / window / app rows

### Configuring apps

| App | Config |
| --- | --- |
| VS Code | `VSCODE_EXECUTABLE_PATH` or PATH `code` / common install paths |
| Chrome | `CHROME_EXECUTABLE_PATH` or common install paths |
| Gmail | `GMAIL_URL` (HTTPS) opened via Chrome; session dedupe avoids repeat opens |
| Teams | `TEAMS_EXECUTABLE_PATH` or discovered Start App |
| WhatsApp | `WHATSAPP_EXECUTABLE_PATH` or Start App / optional Web fallback in config |
| Spotify | `SPOTIFY_EXECUTABLE_PATH`, `spotify:` URI, or Start App |
| News | `NEWS_URL` (HTTPS) opened via Chrome |

Jarvis does **not** read Gmail, Teams, WhatsApp, or news content. No API key or paid service is required.

### Workspace troubleshooting

| Issue | What to do |
| --- | --- |
| Executable not found | Set the matching `*_EXECUTABLE_PATH` in `.env`; verify with `-Status` |
| Teams Store install | Use `list_start_apps.py --filter teams`; Start App launch must be enabled |
| WhatsApp Store install | Same pattern with `--filter whatsapp` |
| Spotify URI | Ensure Spotify is installed and `spotify:` is registered; try executable path |
| Foreground denied | Expected on Windows; app still counts as running / restored |
| Chrome tab duplication | Same activation session dedupes Gmail/news URLs; exact tab focus needs a later extension |
| pywin32 import errors | Reinstall `pywin32` and run `python -m pywin32_postinstall -install` |

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
2. Install Piper + `en_GB-alan-medium` for spoken welcome
3. Ensure `WORKSPACE_ENABLED=true` and `WORKSPACE_START_AFTER_WELCOME=true`
4. Start the app or run `.\scripts\test-wake-listener.ps1`
5. Say clearly: **Wake up, Jarvis.**
6. Expect:
   - Welcome speech (three lines)
   - Assistant: `PROCESSING` → `SPEAKING` → `INITIALIZING_WORKSPACE` → `OPENING_APPLICATIONS` → `READY` → `LISTENING`
   - Dashboard workspace progress for each configured app
   - Microphone resumes only after workspace finishes

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
# Manual workspace without TTS:
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/workspace/start
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

- `backend/` — FastAPI app, StateManager, WebSocket, voice + TTS + workspace services
- `backend/config/applications.json` — approved workspace application registry
- `backend/models/` — Vosk model install location (binaries not committed)
- `backend/voices/` — Piper voice install location (binaries not committed)
- `backend/tools/` — `test_wake_phrase.py`, `test_tts.py`, `list_windows.py`, `list_start_apps.py`, `test_workspace.py`
- `frontend/` — React dashboard
- `scripts/` — PowerShell helpers including workspace / wake / TTS testers
- `docs/` — Architecture, development, and phase roadmap

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Development](docs/DEVELOPMENT.md)
- [Phases](docs/PHASES.md)
- [Vosk model setup](backend/models/README.md)
- [Piper voice setup](backend/voices/README.md)

## License

MIT — see [LICENSE](LICENSE).
