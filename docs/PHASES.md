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

## Phase 2 (complete) — Offline wake-phrase detection

- Offline wake-phrase recognition via Vosk (“Wake up, Jarvis.”)
- Microphone discovery and session selection (`sounddevice`)
- Voice-service lifecycle (start / stop / device change / clean shutdown)
- WebSocket voice events and dashboard activation feedback
- Local-only processing — no cloud speech APIs or API keys

## Phase 3 (current) — Offline British male text-to-speech

- Offline Piper text-to-speech
- British male voice (`en_GB-alan-medium`)
- Fixed three-line welcome sequence
- Microphone suppression during speech (self-voice prevention)
- `ActivationCoordinator` owns wake → speech → resume flow
- Speech-status dashboard and output-device selection

## Future phases

### Windows application launching and focusing

Open and focus VS Code, Chrome, Gmail, Microsoft Teams, WhatsApp, Spotify, and related targets.

### Advanced cinematic dashboard

Richer visuals and motion beyond the foundation shell.

### System monitoring graphs

Expand beyond CPU/memory to GPU, disk, network, battery, and process lists with charts.

### Application command centre

Clickable live grid of open / controlled applications.

### Calendar and email

Unread mail counts and calendar summaries through dedicated integration adapters.

### News and current affairs

Headlines for the dashboard / news tile.

### Local AI

Optional on-device reasoning behind `IntegrationService`.

### Productivity modes

Structured routines beyond the fixed welcome sequence.

### Windows startup packaging

Package the assistant for convenient Windows startup / background operation.
