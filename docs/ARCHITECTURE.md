# Architecture

Jarvis Workspace is a local monorepo with a clear split between a Python backend (control plane) and a React frontend (presentation plane). Phase 1 established communication and the dashboard shell. Phase 2 added offline wake-phrase detection. Phase 3 adds offline Piper TTS and coordinates wake → welcome speech.

## Backend responsibilities

- Expose HTTP APIs for health, assistant state, voice control, and TTS
- Own the assistant lifecycle via `StateManager`
- Broadcast state, voice, and TTS events over WebSocket
- Collect basic host metrics (CPU / memory) with `psutil`
- Own the Windows microphone stream (`VoiceService`)
- Own speech synthesis/playback (`TtsService` + Piper)
- Coordinate wake → speech → resume via `ActivationCoordinator`
- Host placeholders for later phases (`WorkspaceService`, `IntegrationService`)

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

The FastAPI event loop reference is captured during voice startup. Recognition never creates a new event loop per wake. On activation:

1. Publishes `voice.wake_detected`
2. Hands control to `ActivationCoordinator` (Phase 3)
3. Coordinator pauses the microphone, runs TTS, then resumes listening

Phase 2’s short auto-return-to-`LISTENING` timer is disabled when the coordinator is bound (`set_activation_handoff(True)`), so it cannot overwrite `SPEAKING`.

### Why one service owns the microphone

Only `VoiceService` opens the input stream. During speech, `ActivationCoordinator` calls `pause_listening()` / `resume_listening()` so Jarvis cannot hear itself. Future application launching should wait until the welcome sequence finishes.

### Confidence calculation

When Vosk returns per-word `conf` values, confidence is the arithmetic mean of those values. If the normalized text exactly matches the wake phrase but word confidences are absent, confidence defaults to `1.0`. Activation requires `confidence >= WAKE_CONFIDENCE_THRESHOLD`.

## Phase 3 TTS architecture

### Wake-to-speech flow

1. Wake phrase confirmed → `voice.wake_detected`
2. `ActivationCoordinator` starts (rejects duplicates)
3. Assistant → `PROCESSING`
4. Microphone paused + input queue cleared
5. Pre-speech delay
6. Assistant → `SPEAKING`
7. `TtsService` speaks three fixed utterances with pauses
8. Post-speech delay + clear stale audio
9. Microphone resumed
10. Assistant → `LISTENING`

### Component roles

| Component | Responsibility |
| --- | --- |
| `PiperEngine` | Validate Piper + voice files; synthesize WAV via subprocess (`shell=False`) |
| `AudioPlayer` | Play one WAV at a time on the selected output device |
| `SpeechQueue` | Ordered, bounded welcome utterances |
| `TtsService` | TTS lifecycle, sequence events, cancel/retry |
| `ActivationCoordinator` | Authoritative wake → speech → resume orchestration |

### Microphone muting

Self-voice suppression in Phase 3 is controlled muting (stop capture), not acoustic echo cancellation.

## Why separate services?

Voice, workspace control, and integrations have different failure modes, dependencies, and permissions:

| Service | Focus | Why separate |
| --- | --- | --- |
| `VoiceService` | Wake phrase / mic ownership | Capture devices and Vosk |
| `TtsService` | Piper synthesis + playback | Output devices and voice models |
| `WorkspaceService` | Launch / focus apps | Windows process automation |
| `IntegrationService` | Calendar, email, news, local AI | External credentials and network I/O |

Keeping them isolated prevents the core API and StateManager from coupling to optional subsystems. Voice/TTS failures must not prevent health/state/dashboard APIs from working.

## How later phases plug in

Typical extension path:

1. Extend `ActivationCoordinator` after welcome speech (for example open workspace apps)
2. Drive `StateManager` transitions (`OPENING_APPLICATIONS`, etc.)
3. Publish additional WebSocket event types using `WebSocketMessage`
4. Extend dashboard pages to consume the new events / APIs
5. Keep health, state, and connection plumbing unchanged
