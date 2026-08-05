# Architecture

Jarvis Workspace is a local monorepo with a clear split between a Python backend (control plane) and a React frontend (presentation plane). Phase 1 established communication and the dashboard shell. Phase 2 added offline wake-phrase detection. Phase 3 adds offline Piper TTS. Phase 4 adds Windows workspace application launch / restore / focus after the welcome sequence.

## Backend responsibilities

- Expose HTTP APIs for health, assistant state, voice control, TTS, and workspace
- Own the assistant lifecycle via `StateManager`
- Broadcast state, voice, TTS, and workspace events over WebSocket
- Collect basic host metrics (CPU / memory) with `psutil`
- Own the Windows microphone stream (`VoiceService`)
- Own speech synthesis/playback (`TtsService` + Piper)
- Own Windows application control (`WorkspaceService` + registry / process / window helpers)
- Coordinate wake → speech → workspace → resume via `ActivationCoordinator`
- Host placeholders for later phases (`IntegrationService`)

The backend is intentionally free of UI concerns. It does not render dashboards or store presentation preferences.

## Frontend responsibilities

- Render the dashboard shell (Home, System, Applications, Settings)
- Maintain a single WebSocket connection through `useJarvisSocket`
- Poll `/api/health` for live CPU and memory values
- Load and update voice, TTS, and workspace status via REST + WebSocket
- Display connection status, assistant state, wake activation, and workspace progress
- Provide manual Start / Cancel / Open / Focus controls for approved applications only
- Keep unfinished features visibly marked as later-phase placeholders

The frontend never invents system metrics or application control status. The browser does **not** capture microphone audio. Application launches always go through approved backend definitions — never arbitrary shell commands.

## StateManager

`StateManager` is the single source of truth for assistant lifecycle state.

- Valid states live in the `AssistantState` enum
- Current state, previous state, and change timestamp are stored together
- Transitions are protected by an `asyncio.Lock` for FastAPI concurrency
- Invalid values raise `InvalidStateError` and are rejected by the HTTP API
- Every successful transition publishes a `state.changed` event on the in-process `EventBus`

Voice-service lifecycle states (`LISTENING`, `MODEL_MISSING`, etc. on `VoiceServiceStatus`) are separate from assistant states.

Application code should obtain the manager from `app.state.state_manager` rather than importing mutable globals.

## WebSocket event flow

1. Client connects to `/ws`
2. Server accepts the connection and sends `connection.established`
3. Server immediately sends the current assistant state as `state.changed`
4. Server immediately sends the current voice status as `voice.status_changed`
5. Server immediately sends TTS status and current `workspace.status_changed`
6. When `StateManager.set_state` succeeds, the EventBus notifies `ConnectionManager`
7. Voice, TTS, and workspace events are likewise broadcast
8. On disconnect, the client is removed from the connection set
9. The frontend reconnects with capped exponential backoff and refreshes status over HTTP

All messages use the shared envelope:

```json
{
  "type": "string",
  "timestamp": "ISO timestamp",
  "payload": {}
}
```

Raw microphone audio and continuous transcripts are never sent over WebSocket.

## Phase 2 voice architecture

### Components

| Component | Responsibility |
| --- | --- |
| `AudioDeviceManager` | List / validate input devices; never opens the stream |
| `WakePhraseDetector` | Load Vosk once; normalize + match “wake up jarvis”; cooldown + confidence |
| `VoiceService` | Own the single mic stream, audio queue, recognition worker, and event bridge |

### Audio capture flow

1. `VoiceService` resolves the configured or default input device
2. Opens one `sounddevice` input stream (mono float32)
3. Prefers 16 kHz; if unsupported, opens at the device native rate and linearly resamples to 16 kHz
4. The sounddevice callback only copies PCM into a bounded thread-safe queue (no recognition, no async I/O)
5. If the queue is full, oldest frames are dropped and a warning is logged

### Recognition-worker flow

1. A single daemon worker thread dequeues PCM blocks
2. Feeds them to the Vosk recognizer (restricted grammar)
3. On a final result, normalizes text and evaluates exact wake-phrase match + confidence
4. On activation, schedules work on the FastAPI loop via `asyncio.run_coroutine_threadsafe`

### Thread-to-async event bridge

The FastAPI event loop reference is captured during voice startup. Recognition never creates a new event loop per wake. On activation:

1. Publishes `voice.wake_detected`
2. Hands control to `ActivationCoordinator`
3. Coordinator pauses the microphone, runs TTS, launches the workspace, then resumes listening

Phase 2’s short auto-return-to-`LISTENING` timer is disabled when the coordinator is bound (`set_activation_handoff(True)`), so it cannot overwrite `SPEAKING`, `INITIALIZING_WORKSPACE`, `OPENING_APPLICATIONS`, or `READY`.

### Why one service owns the microphone

Only `VoiceService` opens the input stream. During speech and workspace launch, `ActivationCoordinator` keeps the microphone paused via `pause_listening()` / `resume_listening()` so Jarvis cannot hear itself and delayed resume tasks cannot overwrite workspace states.

### Confidence calculation

When Vosk returns per-word `conf` values, confidence is the arithmetic mean of those values. If the normalized text exactly matches the wake phrase but word confidences are absent, confidence defaults to `1.0`. Activation requires `confidence >= WAKE_CONFIDENCE_THRESHOLD`.

## Phase 3 TTS architecture

### Wake-to-speech flow (Phase 3 portion)

1. Wake phrase confirmed → `voice.wake_detected`
2. `ActivationCoordinator` starts (rejects duplicates)
3. Assistant → `PROCESSING`
4. Microphone paused + input queue cleared
5. Pre-speech delay
6. Assistant → `SPEAKING`
7. `TtsService` speaks three fixed utterances with pauses
8. Post-speech delay + clear stale audio
9. Phase 4 continues with workspace launch (microphone still paused)

### Component roles

| Component | Responsibility |
| --- | --- |
| `PiperEngine` | Validate Piper + voice files; synthesize WAV via subprocess (`shell=False`) |
| `AudioPlayer` | Play one WAV at a time on the selected output device |
| `SpeechQueue` | Ordered, bounded welcome utterances |
| `TtsService` | TTS lifecycle, sequence events, cancel/retry |
| `ActivationCoordinator` | Authoritative wake → speech → workspace → resume orchestration |

### Microphone muting

Self-voice suppression is controlled muting (stop capture), not acoustic echo cancellation. The microphone resumes only after workspace completion, safe failure, or cancellation.

## Phase 4 workspace architecture

### Wake-to-workspace flow

1. Welcome speech finishes (“Opening your workspace now.”)
2. Publish `assistant.workspace_initialization_started`
3. Assistant → `INITIALIZING_WORKSPACE` → `OPENING_APPLICATIONS`
4. `WorkspaceService.start_default_workspace()` runs sequentially
5. Per-application progress published as `workspace.application_status` / `workspace.application_result`
6. Final `workspace.run_finished` with `READY`, `PARTIAL_SUCCESS`, `ERROR`, or `CANCELLED`
7. Assistant → `READY` (brief configurable display)
8. Microphone resumed
9. Assistant → `LISTENING`

If welcome TTS fails, workspace launch is skipped by default (`WORKSPACE_START_AFTER_WELCOME` still requires successful speech). Manual `POST /api/workspace/start` can launch without TTS.

### Application registry

Trusted definitions live in `backend/config/applications.json` and are validated by Pydantic (`ApplicationDefinition`). Launch types: `executable`, `url`, `uri`, `start_app`, `browser_url`. Frontend cannot submit arbitrary executables or shell commands.

### Resolution and control

| Component | Responsibility |
| --- | --- |
| `AppRegistry` | Load / validate / order enabled applications |
| `ExecutableResolver` | Configured path → PATH → App Paths → common install locations |
| `StartAppResolver` | Discover Start Menu apps via fixed PowerShell (`shell=False`) |
| `ProcessManager` | Find processes by approved names (`psutil`) |
| `WindowManager` | Enumerate / restore / best-effort focus (`pywin32` adapter) |
| `BrowserController` | Open approved HTTPS URLs in Chrome; session dedupe |
| `ApplicationController` | Decide launch / restore / focus / skip for one app |
| `WorkspaceService` | Sequential lifecycle, cancellation, WebSocket status |

### Security boundary

- No `shell=True`, no `/run-command`, no raw PowerShell from the frontend
- URLs must be HTTPS (localhost HTTP only in development when allowed)
- `spotify:` and similar URIs are allow-listed in definitions, not free-form frontend input
- Focus denial is limited success when the process is running — not a full workspace failure
- Window titles are omitted from logs/payloads unless debug discovery is enabled
- Gmail / Teams / WhatsApp / news content is never read

### Workspace WebSocket events

`workspace.status_changed`, `workspace.run_started`, `workspace.application_status`, `workspace.application_result`, `workspace.run_finished`, `workspace.run_cancelled`, `workspace.warning`, `workspace.error`, plus assistant events `assistant.workspace_initialization_started` and `assistant.workspace_ready`.

## Why separate services?

Voice, workspace control, and integrations have different failure modes, dependencies, and permissions:

| Service | Focus | Why separate |
| --- | --- | --- |
| `VoiceService` | Wake phrase / mic ownership | Capture devices and Vosk |
| `TtsService` | Piper synthesis + playback | Output devices and voice models |
| `WorkspaceService` | Launch / focus apps | Windows process / window automation |
| `IntegrationService` | Calendar, email, news, local AI | External credentials and network I/O |

Keeping them isolated prevents the core API and StateManager from coupling to optional subsystems. Voice/TTS/workspace failures must not prevent health/state/dashboard APIs from working.

## How later phases plug in

Typical extension path:

1. Extend dashboard / APIs for richer application command-centre behaviour
2. Keep approved-application security boundary intact
3. Publish additional WebSocket event types using `WebSocketMessage`
4. Keep health, state, and connection plumbing unchanged
