# Architecture

Jarvis Workspace is a local monorepo with a clear split between a Python backend (control plane) and a React frontend (presentation plane). Phase 1 establishes communication, state, and extension points without implementing voice or automation.

## Backend responsibilities

- Expose HTTP APIs for health and assistant state
- Own the assistant lifecycle via `StateManager`
- Broadcast state changes over WebSocket
- Collect basic host metrics (CPU / memory) with `psutil`
- Provide structured logging to the terminal and `backend/logs/jarvis.log`
- Host placeholder services for later phases (`VoiceService`, `WorkspaceService`, `IntegrationService`)

The backend is intentionally free of UI concerns. It does not render dashboards or store presentation preferences.

## Frontend responsibilities

- Render the Phase 1 dashboard shell (Home, System, Applications, Settings)
- Maintain a single WebSocket connection through `useJarvisSocket`
- Poll `/api/health` for live CPU and memory values
- Display connection status and assistant state clearly
- Keep unfinished features visibly marked as later-phase placeholders

The frontend never invents system metrics or application control status.

## StateManager

`StateManager` is the single source of truth for assistant lifecycle state.

- Valid states live in the `AssistantState` enum
- Current state, previous state, and change timestamp are stored together
- Transitions are protected by an `asyncio.Lock` for FastAPI concurrency
- Invalid values raise `InvalidStateError` and are rejected by the HTTP API
- Every successful transition publishes a `state.changed` event on the in-process `EventBus`

Application code should obtain the manager from `app.state.state_manager` rather than importing mutable globals.

## WebSocket event flow

1. Client connects to `/ws`
2. Server accepts the connection and sends `connection.established`
3. Server immediately sends the current state as `state.changed`
4. When `StateManager.set_state` succeeds, the EventBus notifies `ConnectionManager`
5. `ConnectionManager` broadcasts `state.changed` to all connected clients
6. On disconnect, the client is removed from the connection set
7. The frontend reconnects with capped exponential backoff after unexpected closes

All messages use the shared envelope:

```json
{
  "type": "string",
  "timestamp": "ISO timestamp",
  "payload": {}
}
```

## Why separate placeholder services?

Voice, workspace control, and integrations have different failure modes, dependencies, and permissions:

| Service | Future focus | Why separate |
| --- | --- | --- |
| `VoiceService` | Wake phrase, STT, TTS | Audio devices and model runtimes |
| `WorkspaceService` | Launch / focus apps | Windows process automation |
| `IntegrationService` | Calendar, email, news, local AI | External credentials and network I/O |

Keeping them isolated prevents the core API and StateManager from coupling to optional subsystems. Later phases can replace placeholder methods with real implementations without reshaping HTTP or WebSocket contracts.

## How later phases plug in

Typical extension path:

1. Implement methods inside the relevant placeholder service
2. Drive `StateManager` transitions (`LISTENING`, `SPEAKING`, `OPENING_APPLICATIONS`, etc.)
3. Publish additional WebSocket event types using `WebSocketMessage`
4. Extend dashboard pages to consume the new events / APIs
5. Keep health, state, and connection plumbing unchanged

Phase 1 already wires the placeholder instances onto `app.state` so future work has a stable attachment point.
