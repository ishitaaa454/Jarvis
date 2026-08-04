# Phases

## Phase 1 (complete)

- Project foundation and monorepo layout
- FastAPI backend with health + state APIs
- WebSocket connection and state broadcast
- Central `StateManager` with future lifecycle states reserved
- React dashboard shell (Home, System, Applications, Settings)
- Real CPU / memory via `psutil` health polling
- PowerShell development scripts and documentation
- Backend pytest coverage for health, state, and WebSocket basics

## Phase 2 (current) — Offline wake-phrase detection

- Offline wake-phrase recognition via Vosk (“Wake up, Jarvis.”)
- Microphone discovery and session selection (`sounddevice`)
- Voice-service lifecycle (start / stop / device change / clean shutdown)
- WebSocket voice events and dashboard activation feedback
- Local-only processing — no cloud speech APIs or API keys

## Future phases

### British male text-to-speech

Speak welcome and status lines with a deep British male TTS profile.

### Echo and self-voice suppression

Prevent the assistant from activating on its own spoken output while TTS is active.

### Windows application control

Open and focus VS Code, Chrome, Gmail, Microsoft Teams, WhatsApp, Spotify, and related targets.

### Advanced dashboard

Richer visuals and motion beyond the foundation shell (not the Phase 2 activation banner).

### System monitoring graphs

Expand beyond CPU/memory to GPU, disk, network, battery, and process lists with real data and charts.

### Application command centre

Clickable live grid of open / controlled applications.

### Calendar and email

Unread mail counts and calendar summaries through dedicated integration adapters.

### News

Current-affairs headlines for the dashboard / news tile.

### Local AI

Optional on-device reasoning (for example via a local runtime) behind `IntegrationService`.

### Windows startup packaging

Package the assistant for convenient Windows startup / background operation.
