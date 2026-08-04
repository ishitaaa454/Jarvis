# Jarvis Workspace

Phase 1 foundation for a local Windows desktop assistant. This monorepo provides a FastAPI backend, a React + TypeScript dashboard, WebSocket state sync, and a clean architecture for later voice, workspace, and integration features.

**Phase 1 does not include** wake-word detection, speech recognition, TTS, application launching, email, calendar, news, or local AI.

## Prerequisites

- Windows 10/11
- Python 3.11+
- Node.js 18+ (20+ recommended)
- PowerShell

## Setup (PowerShell)

Run these from the `jarvis-workspace` folder unless noted.

### 1. Check Python and Node versions

```powershell
python --version
node --version
npm --version
```

### 2. Create the Python virtual environment

```powershell
cd backend
python -m venv .venv
```

### 3. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If activation is blocked by execution policy:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 4. Install backend dependencies

```powershell
pip install -r requirements-dev.txt
```

### 5. Install frontend dependencies

```powershell
cd ..\frontend
npm install
```

### 6. Create local `.env` files from examples

```powershell
cd ..\backend
Copy-Item .env.example .env

cd ..\frontend
Copy-Item .env.example .env
```

### 7. Start backend only

```powershell
cd ..\scripts
.\start-backend.ps1
```

Or manually:

```powershell
cd ..\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
```

### 8. Start frontend only

```powershell
cd ..\scripts
.\start-frontend.ps1
```

Or manually:

```powershell
cd ..\frontend
npm run dev
```

### 9. Start both using the development script

```powershell
cd scripts
.\start-development.ps1
```

### 10. Run backend tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q
```

### 11. Run the frontend production build

```powershell
cd frontend
npm run typecheck
npm run build
```

### 12. Open the application in the browser

- Dashboard: http://localhost:5173
- Health API: http://127.0.0.1:8765/api/health
- State API: http://127.0.0.1:8765/api/state
- WebSocket: ws://127.0.0.1:8765/ws

### 13. Stopping the services

- In each PowerShell window running Uvicorn or Vite, press `Ctrl+C`
- Close the extra windows opened by `start-development.ps1` when finished

## Project layout

- `backend/` — FastAPI app, StateManager, WebSocket, health API
- `frontend/` — React dashboard shell
- `scripts/` — PowerShell helpers
- `docs/` — Architecture, development, and phase roadmap

## Phase 1 verification tip

Force a state change and watch the dashboard update:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/state/LISTENING
```

Then return to idle:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/state/IDLE
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Development](docs/DEVELOPMENT.md)
- [Phases](docs/PHASES.md)

## License

MIT — see [LICENSE](LICENSE).
