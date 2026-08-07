"""Phase 7 window inventory API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import Response as FastAPIResponse

from app.models.window import PreviewAvailability

router = APIRouter(prefix="/api/windows", tags=["windows"])


def _inventory(request: Request):
    service = getattr(request.app.state, "window_inventory_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Window inventory unavailable")
    return service


def _previews(request: Request):
    return getattr(request.app.state, "window_preview_provider", None)


@router.get("")
async def list_windows(request: Request) -> dict:
    snap = _inventory(request).get_snapshot()
    return snap.model_dump(mode="json")


@router.get("/recent")
async def recent_windows(request: Request) -> dict:
    items = _inventory(request).get_recent()
    return {"recent": [item.model_dump(mode="json") for item in items]}


@router.post("/refresh")
async def refresh_windows(request: Request) -> dict:
    service = _inventory(request)
    await service.request_refresh()
    snap = await service.refresh_now()
    return {"accepted": True, "total_windows": snap.total_windows}


@router.post("/{window_id}/focus")
async def focus_window(window_id: str, request: Request) -> dict:
    result = _inventory(request).focus_window(window_id)
    return result.model_dump(mode="json")


@router.post("/{window_id}/restore")
async def restore_window(window_id: str, request: Request) -> dict:
    result = _inventory(request).restore_window(window_id)
    return result.model_dump(mode="json")


@router.get("/{window_id}/preview")
async def window_preview(window_id: str, request: Request) -> Response:
    provider = _previews(request)
    if provider is None:
        raise HTTPException(status_code=403, detail="Previews unavailable")
    status, data, meta = provider.capture(window_id)
    if status == PreviewAvailability.DISABLED:
        raise HTTPException(status_code=403, detail="Previews disabled")
    if status == PreviewAvailability.BLOCKED:
        raise HTTPException(status_code=403, detail="Preview blocked by privacy policy")
    if status == PreviewAvailability.WINDOW_NOT_FOUND:
        raise HTTPException(status_code=404, detail="Window not found")
    if status != PreviewAvailability.AVAILABLE or not data:
        raise HTTPException(status_code=409, detail=meta.reason or "PREVIEW_UNAVAILABLE")
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }
    return FastAPIResponse(content=data, media_type="image/jpeg", headers=headers)
