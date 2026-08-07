"""Phase 7 global hotkey API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/hotkeys", tags=["hotkeys"])


def _service(request: Request):
    service = getattr(request.app.state, "global_hotkey_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Hotkey service unavailable")
    return service


@router.get("/status")
async def hotkey_status(request: Request) -> dict:
    return _service(request).get_status().model_dump(mode="json")


@router.post("/retry")
async def hotkey_retry(request: Request) -> dict:
    status = await _service(request).retry()
    return status.model_dump(mode="json")
