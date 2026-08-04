# Architecture

Jarvis Workspace is a local monorepo with a clear split between a Python backend (control plane) and a React frontend (presentation plane). Phase 1 established communication, state, and the dashboard shell. Phase 2 adds offline wake-phrase detection through a dedicated voice service.

## Backend responsibilities

- Expose HTTP APIs for health, assistant state, and voice control
- Own the assistant lifecycle via `StateManager`
- Broadcast state and voice events over WebSocket
- Collect basic host metrics (CPU / memory) with `psutil`
- Provide structured logging to the terminal and `backend/logs/jarvis.log`
- Own the Windows microphone stream for offline wake-phrase detection (`VoiceService`)
- Host placeholder services for later phases (`WorkspaceService`, `IntegrationService`)

The backend is intentionally free of UI concerns. It does not render dashboards or store presentation preferences.

## Frontend responsibilities

- Render the dashboard shell (Home, System, Applications, Settings)
- Maintain a single WebSocket connection through `useJarvisSocket`
- Poll `/api/health` for live CPU and memory values
- Load and update voice status via REST + WebSocket (`useVoiceStatus`)
- Display connection status, assistant state, and wake activation clearly
- Keep unfinished features visibly marked as later-phase placeholders

The frontend never invents system metrics or application control status. The browser does **not** capture microphone audio in Phase 2.

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
5. When `StateManager.set_state` succeeds, the EventBus notifies `ConnectionManager`
6. Voice events (`voice.status_changed`, `voice.wake_detected`, `voice.error`) are likewise broadcast
7. On disconnect, the client is removed from the connection set
8. The frontend reconnects with capped exponential backoff and refreshes voice status over HTTP

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

The FastAPI event loop reference is captured during voice startup. Recognition never creates a new event loop per wake. The async handler:

1. Publishes `voice.wake_detected`
2. Sets assistant state to `PROCESSING`
3. Schedules a short (~800–1200 ms) return to `LISTENING` without blocking the worker
4. Uses an activation generation counter so overlapping activations do not race

### Why one service owns the microphone

Only `VoiceService` opens the input stream. Device changes stop the existing stream before opening another. Phase 3 TTS will coordinate with this same owner so playback and capture do not fight for exclusive device access — TTS will pause or duck listening rather than opening a second capture path.

### Confidence calculation

When Vosk returns per-word `conf` values, confidence is the arithmetic mean of those values. If the normalized text exactly matches the wake phrase but word confidences are absent, confidence defaults to `1.0`. Activation requires `confidence >= WAKE_CONFIDENCE_THRESHOLD`.

## Why separate services?

Voice, workspace control, and integrations have different failure modes, dependencies, and permissions:

| Service | Focus | Why separate |
| --- | --- | --- |
| `VoiceService` | Wake phrase (Phase 2); STT/TTS later | Audio devices and model runtimes |
| `WorkspaceService` | Launch / focus apps | Windows process automation |
| `IntegrationService` | Calendar, email, news, local AI | External credentials and network I/O |

Keeping them isolated prevents the core API and StateManager from coupling to optional subsystems. Voice failures must not prevent health/state/dashboard APIs from working.

## How later phases plug in

Typical extension path:

1. Extend `VoiceService` (for example `speak()` for British-male TTS) without bypassing microphone ownership
2. Drive `StateManager` transitions (`SPEAKING`, `OPENING_APPLICATIONS`, etc.)
3. Publish additional WebSocket event types using `WebSocketMessage`
4. Extend dashboard pages to consume the new events / APIs
5. Keep health, state, and connection plumbing unchanged
