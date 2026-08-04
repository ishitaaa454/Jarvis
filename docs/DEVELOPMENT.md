# Development Guide

## Coding conventions

- Python: type hints on public functions, Pydantic models for payloads, no silent exception swallowing
- TypeScript: strict mode, small components, CSS modules for scoped styling
- Prefer explicit placeholder messaging over fake “working” behavior
- Keep network traffic local (`127.0.0.1` / `localhost`) in Phase 1
- Do not commit `.env` files or secrets

## Adding a new backend service

1. Create `backend/app/services/your_service.py` (or under `placeholders/` if unfinished)
2. Construct it once in `create_app()` and attach it to `app.state`
3. Inject via `request.app.state` in routers — avoid module-level singletons for mutable state
4. Log meaningful lifecycle events
5. Add focused unit/API tests under `backend/tests/`

## Adding a new WebSocket event

1. Define the payload shape (Pydantic on backend, TypeScript interface on frontend)
2. Build a `WebSocketMessage(type=..., payload=...)`
3. Send via `ConnectionManager.send_json` or `broadcast`
4. Handle the `type` in `useJarvisSocket` / activity logging
5. Document the event in a short comment or architecture note when it becomes part of the public contract

## Adding a new dashboard page

1. Create `frontend/src/pages/YourPage.tsx` (+ CSS module)
2. Register a route in `App.tsx`
3. Add a nav item in `DashboardLayout` / `NavigationDots`
4. Reuse `MetricCard`, `StatusBadge`, and connection state from the shared hook/layout
5. Mark unfinished sections with “Available in a later phase”

## Running tests

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q
```

Frontend validation:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Logging expectations

- Startup and shutdown must appear in the terminal and `backend/logs/jarvis.log`
- Log WebSocket connect / disconnect
- Log every state transition
- Log API client errors at warning level
- Log unexpected exceptions with stack traces on the server only — never return stack traces to the frontend
