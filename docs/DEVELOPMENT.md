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
- TTS coordinates via `pause_listening` / `resume_listening` (Phase 3)
- `ActivationCoordinator` owns the full wake → speech → resume state machine

## Piper / TTS rules

- Keep Piper behind `PiperEngine` (subprocess list args, never `shell=True`)
- Do not auto-download voices at backend startup
- Delete temporary WAVs when `TTS_DELETE_TEMP_AUDIO=true`
- Reject overlapping welcome sequences
- Always attempt to resume the microphone after speech, cancel, or error
- Test TTS without hardware using fake engine/player injection

## Logging and privacy rules

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
4. Reuse `MetricCard`, `StatusBadge`, and connection / voice hooks from the shared layout
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

## Logging expectations

- Startup and shutdown must appear in the terminal and `backend/logs/jarvis.log`
- Log WebSocket connect / disconnect
- Log every assistant state transition
- Log voice start / stop / wake / errors
- Log API client errors at warning level
- Log unexpected exceptions with stack traces on the server only — never return stack traces to the frontend
