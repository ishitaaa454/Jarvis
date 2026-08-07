# Development Guide

## Coding conventions

- Python: type hints on public functions, Pydantic models for payloads, no silent exception swallowing
- TypeScript: strict mode, small components, CSS modules for scoped styling
- Prefer explicit placeholder messaging over fake “working” behavior
- Keep network traffic local (`127.0.0.1` / `localhost`)
- Do not commit `.env` files, secrets, Vosk model binaries, or Piper `.onnx` voices

## Adding a new backend service

1. Create `backend/app/services/your_service.py` (or under `placeholders/` if unfinished)
2. Construct it once in `create_app()` and attach it to `app.state`
3. Inject via `request.app.state` in routers — avoid module-level singletons for mutable state
4. Log meaningful lifecycle events
5. Add focused unit/API tests under `backend/tests/`

## Adding a new WebSocket event

1. Define the payload shape (Pydantic on backend, TypeScript interface on frontend)
2. Add an EventBus constant in `app/core/events.py` when the event is internal too
3. Build a `WebSocketMessage(type=..., payload=...)`
4. Send via `ConnectionManager.send_json` or `broadcast` (subscribe in `register_websocket_broadcasts`)
5. Handle the `type` in `useJarvisSocket` / `useVoiceStatus` / activity logging
6. Never put raw audio or continuous transcripts in WebSocket payloads

## Adding a voice event

1. Publish from `VoiceService` on the EventBus (`VOICE_*` constants)
2. Mirror it in `create_voice_event_handlers` for WebSocket clients
3. Update frontend types under `types/voice.ts` and the socket handlers
4. Prefer REST `GET /api/voice/status` for authoritative snapshots after reconnect

## Audio-thread rules

- The sounddevice callback must do minimal work: copy / enqueue only
- Never run Vosk, network I/O, or `asyncio` APIs inside the callback
- Use one recognition worker thread and a bounded queue
- Bridge back to FastAPI with `asyncio.run_coroutine_threadsafe` on the captured loop
- Do not create a new event loop per wake detection
- Do not busy-wait; use queue timeouts / events

## Microphone ownership rules

- Only `VoiceService` opens the input stream
- Never open a second capture stream for the same session
- Device changes must stop the current stream before opening another
- TTS and workspace coordinate via `pause_listening` / `resume_listening`
- `ActivationCoordinator` owns the full wake → speech → workspace → resume state machine
- Microphone must not resume immediately after TTS when workspace launch is enabled

## Piper / TTS rules

- Keep Piper behind `PiperEngine` (subprocess list args, never `shell=True`)
- Do not auto-download voices at backend startup
- Delete temporary WAVs when `TTS_DELETE_TEMP_AUDIO=true`
- Reject overlapping welcome sequences
- Always attempt to resume the microphone after speech, workspace, cancel, or error
- Test TTS without hardware using fake engine/player injection

## Workspace / application launch rules

### Adding an approved application

1. Add a definition to `backend/config/applications.json` (stable `id`, `launch_type`, process names, order)
2. Prefer PATH / common-path discovery over machine-specific committed paths
3. Put explicit executable overrides in `.env` (`VSCODE_EXECUTABLE_PATH`, etc.)
4. Validate through `AppRegistry` / Pydantic — reject unknown launch types
5. Add unit tests with fakes; do not launch real apps in pytest

### Launch-type rules

- `executable` — trusted resolved path or approved candidate command
- `url` — HTTPS in the default browser
- `browser_url` — HTTPS through configured Chrome
- `uri` — allow-listed protocol such as `spotify:` defined in config, not free-form UI input
- `start_app` — discovered AppUserModelID / Start App entry

### Executable resolution order

1. Explicit configured / env override path
2. Approved PATH candidates
3. Windows App Paths when practical
4. Common install locations via `LOCALAPPDATA` / `PROGRAMFILES` / `PROGRAMFILES(X86)`

Do not scan the whole drive. Do not execute during discovery.

### Window matching rules

- Match by approved process IDs + optional title patterns
- Ignore empty-title and invisible windows
- Restore minimized windows with `ShowWindow(SW_RESTORE)`
- Best-effort `SetForegroundWindow`; focus denial is limited success when running
- Never close or kill user applications in Phase 4

### Safe subprocess rules

- Always `shell=False`
- Argument lists only from verified definitions
- Fixed PowerShell argv for Start App discovery — no user interpolation
- Timeouts on discovery and startup waits

### URL validation rules

- Allow `https://` by default
- Optionally allow `http://localhost` / `127.0.0.1` in development
- Reject `javascript:`, `data:`, `file:`, credentials in URLs, and non-allow-listed protocols

### Testing without launching applications

- Inject fake process / window / Start App / browser dependencies
- Use temporary `applications.json` files
- Keep `WORKSPACE_START_AFTER_WELCOME=false` in pytest conftest so unit tests stay isolated
- Manual live launch: `.\scripts\test-workspace.ps1` (Windows only)

### Logging and privacy

Log: registry load, resolution results, run start/finish, per-app status, focus request outcome, cancellation, shutdown.

Do **not** log: window titles (unless debug), browser cookies, Gmail/Teams/WhatsApp content, email subjects, message text, or raw command lines.

## Logging and privacy rules (voice)

Log: init, model load, selected mic, start/stop, wake detection + confidence, cooldown rejects, device changes, queue overflows, errors, shutdown.

Do **not** log: raw audio, buffers, continuous partial transcripts, or non-matching speech — unless `VOICE_DEBUG_TRANSCRIPTS=true` (mark those lines clearly as development logs).

Do not store microphone recordings.

## Testing voice code without hardware

- Inject a fake `sounddevice` module into `AudioDeviceManager`
- Inject a `WakePhraseDetector` with `model=object()` and a fake recognizer factory
- Inject a fake `stream_factory` into `VoiceService`
- Call `simulate_wake()` / `POST /api/voice/test-activation` (development only) for WebSocket checks
- Unit-test `normalize_wake_text` / `evaluate_recognized_text` as pure functions
- Keep `VOICE_START_AUTOMATICALLY=false` in pytest (`tests/conftest.py`)

## Adding a new dashboard page

1. Create `frontend/src/pages/YourPage.tsx` (+ CSS module)
2. Register a route in `App.tsx`
3. Add a nav item in `DashboardLayout` / `NavigationDots`
4. Reuse `MetricCard`, `StatusBadge`, and connection / voice / workspace hooks from the shared layout
5. Mark unfinished sections with “Available in a later phase”

## Running tests

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q
```

Frontend validation:

```powershell
cd frontend
npm run typecheck
npm run build
```

Manual wake listener (requires model + microphone):

```powershell
cd scripts
.\test-wake-listener.ps1 -ListDevices
.\test-wake-listener.ps1
```

Manual TTS (requires Piper + voice files + speakers):

```powershell
cd scripts
.\test-tts.ps1 -ListDevices
.\test-tts.ps1
```

Manual workspace (Windows + installed apps):

```powershell
cd scripts
.\test-workspace.ps1 -List
.\test-workspace.ps1 -Status
.\test-workspace.ps1 -AppId vscode
.\test-workspace.ps1
.\test-workspace.ps1 -NoFocus
```

## Dashboard development (Phase 5)

### Adding a dashboard panel

1. Extend `DashboardPanelId` / `PANEL_ORDER` / routes
2. Render the panel inside `PanelViewport`
3. Keep Settings outside the swipe track unless intentionally included
4. Avoid a second WebSocket or health poller

### Adding a core state appearance

Map the assistant state in `mapAssistantToCoreState` and add a CSS modifier on `JarvisCore`. Prefer transform/opacity. Respect reduced motion.

### Adding a timeline event

Extend `dispatchDashboardEvent` with a stable id via `makeTimelineId`. Do not append from multiple components for the same event.

### WebSocket rules

- One connection (`useJarvisSocket`)
- One fan-out handler in `DashboardProvider`
- Domain hooks update domain state; dispatcher updates timeline/announcements
- Re-fetch authoritative REST status after reconnect

### Metrics rules

- Core panel may still use shared `useHealthMetrics` for compact CPU/memory sparklines
- System Intelligence uses `useSystemMonitor` + `/api/system-monitor/*` for Phase 6 data
- Bound history; never invent GPU, disk, network, battery, or temperature values
- Show `UNSUPPORTED` / `UNAVAILABLE` / `NOT DETECTED` / `PROVIDER NOT INSTALLED` instead of fake zeroes

### Motion and accessibility

- Use CSS variables `--motion-*` and `--ease-*`
- Disable continuous animation under `prefers-reduced-motion`
- Announce wake, speech start, workspace start/ready, and errors via `aria-live`
- Keep keyboard panel navigation and visible focus rings
- Do not announce every one-second metric tick

### Testing

```powershell
cd frontend
npm test
npm run typecheck
npm run build
```

## System monitoring development (Phase 6)

### Adding a system provider

1. Add a provider module under `backend/app/services/system_monitor/`
2. Return Pydantic models with availability metadata (`null` / reason codes for unsupported fields)
3. Wire it into `SystemMonitorService` with a timeout
4. Update capability detection and tests with fakes — do not require real hardware

### Provider timeout and sampling rules

- One scheduler owns intervals; do not add independent timers per metric
- Reject overlapping sample cycles
- On timeout: record error, continue other providers, avoid backlog

### Rate-calculation rules

- Use monotonic timestamps only
- First sample, zero elapsed, negative delta, NaN/inf → unavailable (not zero)

### Metric-history rules

- Bounded deques only; no database
- Reject NaN/infinity; preserve timestamps
- Allow-list metric names for the history API

### Process privacy requirements

Never collect or expose command lines, executable paths, usernames, environment, open files, network connections, or window titles. No kill/priority endpoints.

### Optional dependencies

- NVIDIA: install `nvidia-ml-py` only when needed (`pip install nvidia-ml-py`)
- LibreHardwareMonitor: optional local tool path via env; never auto-download or auto-elevate

### Manual monitor tool

```powershell
.\scripts\test-system-monitor.ps1 -Snapshot
.\scripts\test-system-monitor.ps1 -Watch -Seconds 30
.\scripts\test-system-monitor.ps1 -Capabilities
.\scripts\test-system-monitor.ps1 -Processes
```

## Logging expectations

- Startup and shutdown must appear in the terminal and `backend/logs/jarvis.log`
- Log WebSocket connect / disconnect
- Log every assistant state transition
- Log voice start / stop / wake / errors
- Log workspace run start / per-app results / finish / cancel
- Log system-monitor start/stop, capability changes, provider failures (not every sample at INFO)
- Log API client errors at warning level
- Log unexpected exceptions with stack traces on the server only — never return stack traces to the frontend
- Never log process command lines, usernames, paths, MAC addresses, or serial numbers
