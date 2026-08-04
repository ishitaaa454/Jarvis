# Phases

## Phase 1 (current)

- Project foundation and monorepo layout
- FastAPI backend with health + state APIs
- WebSocket connection and state broadcast
- Central `StateManager` with future lifecycle states reserved
- React dashboard shell (Home, System, Applications, Settings)
- Real CPU / memory via `psutil` health polling
- PowerShell development scripts and documentation
- Backend pytest coverage for health, state, and WebSocket basics

## Future phases

### Wake-phrase engine

Detect “Wake up, Jarvis.” while the assistant runs quietly in the background.

### British male voice

Speak welcome and status lines with a deep British male TTS profile.

### Windows application control

Open and focus VS Code, Chrome, Gmail, Microsoft Teams, WhatsApp, Spotify, and related targets.

### Advanced dashboard

Richer visuals and motion beyond the Phase 1 foundation shell.

### System monitoring

Expand beyond CPU/memory to GPU, disk, network, battery, and process lists with real data.

### Application grid

Clickable live grid of open / controlled applications.

### Calendar and email

Unread mail counts and calendar summaries through dedicated integration adapters.

### News

Current-affairs headlines for the dashboard / news tile.

### Local AI

Optional on-device reasoning (for example via a local runtime) behind `IntegrationService`.

### Windows startup packaging

Package the assistant for convenient Windows startup / background operation.
