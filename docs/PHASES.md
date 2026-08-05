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

## Phase 4 (complete) — Windows workspace launching

- Windows application launching / restoring / best-effort focusing
- Existing-process detection (`psutil`) and window control (`pywin32`)
- Configurable application registry (`backend/config/applications.json`)
- Gmail and news HTTPS URL opening through Chrome
- Workspace progress events and manual open / focus controls
- Microphone remains paused until workspace launch finishes

## Phase 5 (current) — Advanced cinematic dashboard

- Original dark futuristic Jarvis core (CSS/SVG, no copyrighted artwork)
- Three-panel navigation: Applications · Core · System
- Route synchronisation (`/applications`, `/`, `/system`)
- Mouse drag, touch swipe, keyboard arrows, dots, prev/next controls
- State-driven activation visuals from real WebSocket events
- Structured activity timeline with deduplication
- Real CPU / memory session sparklines (current session only)
- Enhanced application command cards
- Fullscreen control (user gesture required)
- Responsive layout, accessibility announcements, reduced motion
- Vitest + React Testing Library coverage for dashboard logic/UI

Phase 5 does **not** include GPU/disk/network graphs, live thumbnails, calendar, unread email, news aggregation, Ollama, unrestricted voice commands, or Windows packaging.

## Future phases

### Phase 6 — Advanced system monitoring

Disk information, network throughput, battery status, process table, GPU data where supported, hardware temperatures where supported.

### Phase 7 — Rich application command centre

Better app switching, global dashboard shortcut, optional live thumbnails, safer browser integration.

### Phase 8 — Calendar and meetings

Calendar summaries, Gmail unread counts, Outlook integration, Teams meeting links.

### Phase 9 — News and current affairs

RSS feeds, categories, spoken briefing (beyond opening a news URL).

### Phase 10 — Local AI and natural voice commands

Ollama integration and context-aware spoken commands.

### Phase 11 — Productivity modes

Focus, development, work, and relax modes.

### Phase 12 — Windows desktop packaging

System tray, automatic startup, global keyboard shortcut, kiosk-style dashboard mode.
