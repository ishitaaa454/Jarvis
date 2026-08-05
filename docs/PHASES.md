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

## Phase 3 (complete) — Offline British male text-to-speech

- Offline Piper text-to-speech
- British male voice (`en_GB-alan-medium`)
- Fixed three-line welcome sequence
- Microphone suppression during speech (self-voice prevention)
- `ActivationCoordinator` owns wake → speech → resume flow
- Speech-status dashboard and output-device selection

## Phase 4 (current) — Windows workspace launching

- Windows application launching / restoring / best-effort focusing
- Existing-process detection (`psutil`) and window control (`pywin32`)
- Configurable application registry (`backend/config/applications.json`)
- Gmail and news HTTPS URL opening through Chrome
- Workspace progress on the dashboard (per-application status)
- Manual open / focus / start / cancel APIs and development tools
- Microphone remains paused until workspace launch finishes

Phase 4 does **not** include advanced cinematic dashboard graphs, live window previews, calendar, email unread counts, news summarisation, Ollama, unrestricted AI conversation, arbitrary voice commands, or Windows startup packaging.

## Future phases

### Advanced cinematic dashboard

Richer visuals and motion beyond the foundation shell.

### System monitoring graphs

Expand beyond CPU/memory to GPU, disk, network, battery, and process lists with charts.

### Application command centre

Clickable live grid of open / controlled applications with richer switching.

### Live window previews

Thumbnail / preview surfaces for open applications.

### Calendar and email

Unread mail counts and calendar summaries through dedicated integration adapters.

### News and current affairs

Headlines for the dashboard / news tile (beyond opening a news URL).

### Natural voice commands

Structured spoken commands beyond the fixed wake phrase and welcome sequence.

### Local AI

Optional on-device reasoning behind `IntegrationService` (for example Ollama).

### Productivity modes

Structured routines beyond the fixed welcome + workspace launch.

### Global keyboard shortcut

Bring the dashboard or assistant forward without voice.

### Windows startup packaging

Package the assistant for convenient Windows startup / background operation.
