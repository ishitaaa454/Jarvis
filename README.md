# Jarvis Workspace

Local Windows desktop assistant. Phases 1–6 delivered wake phrase, Piper TTS, workspace launching, cinematic dashboard, and advanced system monitoring. **Phase 7** upgrades the Applications panel into a rich Application Command Centre with multi-window switching, Ctrl+Alt+J return-to-Jarvis, safer browser destinations, and optional privacy-controlled previews.

**Phase 7 does not include** calendar, unread email, news aggregation, Ollama, process killing, keyboard logging, cookie access, or Windows packaging. All features remain local — no paid API is required.

## Phase 7 — Application Command Centre

### Using the Command Centre

Open `/applications`. Favourites sit at the top. Expand an application to see its safe windows, then **Switch** or **Restore**. Search filters approved app names and safe titles only.

### Global shortcut

Default: **Ctrl + Alt + J** (RegisterHotKey). Returns toward the Jarvis dashboard (opens/focuses the dashboard destination and Chrome). Conflicts are reported in Settings / Command Centre. Jarvis does **not** log other keystrokes.

```powershell
.\scripts\test-command-centre.ps1 -Hotkey
```

### Browser destinations

Dashboard, Gmail, and News use session tracking by default. Exact tab focus requires optional Chrome DevTools on loopback (`BROWSER_CDP_ENABLED=true`, port 9222) — never enabled automatically, never accesses cookies or page JavaScript.

### Window title privacy

Default `WINDOW_TITLE_MODE=SAFE`. Gmail, Teams, WhatsApp, and Spotify never expose private titles. Raw HWND values are never sent to the frontend.

### Window previews

Disabled by default (`WINDOW_PREVIEWS_ENABLED=false`). Sensitive apps (Gmail/Teams/WhatsApp) are blocked unless `ALLOW_SENSITIVE_APP_PREVIEWS=true`. Previews are in-memory only with `Cache-Control: no-store`.

### Manual tools

```powershell
.\scripts\test-command-centre.ps1 -Windows
.\scripts\test-command-centre.ps1 -Recent
.\scripts\test-command-centre.ps1 -AppId vscode
.\scripts\test-command-centre.ps1 -Browser
.\scripts\test-command-centre.ps1 -Destination gmail
```

---

## Phase 6 — Advanced local system monitoring

### Starting system monitoring

Monitoring starts with the backend when `SYSTEM_MONITOR_ENABLED=true` and `SYSTEM_MONITOR_START_AUTOMATICALLY=true` (defaults in `.env.example`). Open the System panel (`/system`) to browse Overview, CPU, Memory, Storage, Network, Power, GPU, Temperatures, Processes, and Capabilities.

```powershell
cd scripts
.\start-development.ps1
```

### Live session history

Charts show **LIVE SESSION HISTORY** only — bounded in-memory samples (~5 minutes at 1s). History resets when the backend restarts. It is not long-term storage.

### What is monitored

| Area | Behaviour |
| --- | --- |
| CPU | Overall %, per-core %, frequency when available, core counts |
| Memory / swap | Bytes + %, binary units (KiB/MiB/GiB) |
| Disks | Fixed-drive capacity; aggregate read/write rates (not falsely assigned per drive) |
| Network | Receive/send rates and adapter table (no MAC addresses by default) |
| Battery | Real status, or **NO BATTERY DETECTED** on desktops |
| Processes | Read-only name/PID/CPU/memory/status — no cmdline, path, username, or kill |
| GPU | Optional NVIDIA NVML; otherwise clear unsupported/provider-missing state |
| Temperatures | Optional `psutil` / LibreHardwareMonitor; otherwise provider-not-available |

Unsupported metrics are never shown as `0`. States include `UNSUPPORTED`, `UNAVAILABLE`, `PERMISSION LIMITED`, `NOT DETECTED`, `PROVIDER NOT INSTALLED`, `DATA PENDING`.

### Freshness

Metric groups show `LIVE`, `DELAYED`, `STALE`, or `UNAVAILABLE` from backend timestamps. On WebSocket disconnect, last values remain but are marked STALE.

### Optional NVIDIA GPU monitoring

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install nvidia-ml-py
```

Set `GPU_MONITOR_ENABLED=true` and `NVIDIA_NVML_ENABLED=true`. If NVML, drivers, or an NVIDIA GPU are missing, the backend still runs and the UI explains why GPU data is unavailable.

### Optional LibreHardwareMonitor temperatures

Do not auto-download. Install LibreHardwareMonitor yourself if desired, then set:

```
TEMPERATURE_MONITOR_ENABLED=true
LIBRE_HARDWARE_MONITOR_ENABLED=true
LIBRE_HARDWARE_MONITOR_PATH=C:\path\to\LibreHardwareMonitor
```

Paths are never exposed through API responses.

### Manual monitor tests

```powershell
.\scripts\test-system-monitor.ps1 -Snapshot
.\scripts\test-system-monitor.ps1 -Watch -Seconds 30
.\scripts\test-system-monitor.ps1 -Processes
.\scripts\test-system-monitor.ps1 -Capabilities
.\scripts\test-system-monitor.ps1 -Gpu
.\scripts\test-system-monitor.ps1 -Temperatures
```

### Process privacy

Jarvis cannot kill processes, change priority, or show command lines / usernames / executable paths. Access-denied processes are skipped safely.

### Troubleshooting

| Symptom | Check |
| --- | --- |
| Provider failure | Capabilities panel + backend log; use Retry where offered |
| Access-denied processes | Expected for protected OS processes; `limited_count` rises |
| No battery data | Normal on desktops — not an error |
| GPU errors | Optional package/drivers; monitoring continues without GPU |
| Temperature missing | Common on Windows without sensors / LHM |

---

## Phase 5 — Cinematic dashboard

### Start the dashboard

```powershell
cd scripts
.\start-development.ps1
```

Open http://localhost:5173 — Core panel is the default.

### Navigate between panels

| Control | Behaviour |
| --- | --- |
| Routes | `/applications`, `/` (Core), `/system`, `/settings` |
| Arrow keys | ← previous · → next · Home returns to Core |
| Mouse drag / trackpad | Horizontal drag snaps to the next panel |
| Touch swipe | Same as drag |
| Navigation dots / labels | Jump directly |
| Prev / Next buttons | Step one panel |
| Browser Back / Forward | Restores the matching panel |

Settings is a separate page (not part of the swipe track).

### Fullscreen

Use **Enter Fullscreen** in the header. Browsers require a user click — Jarvis cannot enter fullscreen automatically after “Wake up, Jarvis.” Escape exits fullscreen. Full kiosk mode belongs to a later packaging phase.

### Jarvis core states

The core reacts to real assistant state: offline, listening, processing, speaking, initializing workspace, opening applications, ready, error. Speaking shows the current sentence and `1/3`…`3/3`. Workspace opening shows the current app and `n/7` progress from the backend.

### Activity timeline

Events are categorised (SYSTEM, VOICE, SPEECH, WORKSPACE, APPLICATION, CONNECTION, ERROR). Replayed WebSocket events are deduplicated. Clear only affects the local UI timeline — backend logs are unchanged. Window titles are not shown. System-monitor timeline entries are significant changes only (start/degraded/capability), not every CPU tick.

### Application cards

Cards use Phase 4 status only: Active, Background, Ready to launch, Not configured, Action failed, and focus-limited running. Open / Focus call approved APIs. No branded logos — letter initials only.

### Metrics

CPU and memory remain available via `/api/health` for Core sparklines. Phase 6 System panel uses `/api/system-monitor/*` and WebSocket `system.*` events for full monitoring. Charts are **live session history** only.

### Connection loss

Disconnected clients show CONNECTION LOST / STALE. On reconnect, voice, TTS, workspace, health, system monitor, and assistant state are refreshed. No second WebSocket is opened.

### Reduced motion

`prefers-reduced-motion: reduce` disables continuous ring rotation and decorative drift. Settings can override. Tab hide pauses decorative ambient motion; WebSocket handling continues.

### Returning after focusing an app

Focus may place another window in front. Use Alt+Tab or the taskbar. A future global shortcut is planned.

No paid API or cloud service is required for the dashboard.


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
npm test
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
