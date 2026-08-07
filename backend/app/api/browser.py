"""Phase 7 browser integration API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/browser", tags=["browser"])


def _service(request: Request):
    service = getattr(request.app.state, "browser_integration_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Browser integration unavailable")
    return service


@router.get("/status")
async def browser_status(request: Request) -> dict:
    return _service(request).get_status().model_dump(mode="json")


@router.get("/destinations")
async def browser_destinations(request: Request) -> dict:
    items = _service(request).list_destinations()
    return {"destinations": [item.model_dump(mode="json") for item in items]}


@router.post("/destinations/{destination_id}/open")
async def open_destination(destination_id: str, request: Request) -> dict:
    result = await _service(request).open_destination(destination_id)
    if result.result == "REJECTED":
        raise HTTPException(status_code=404, detail=result.error or "Unknown destination")
    return result.model_dump(mode="json")


@router.post("/destinations/{destination_id}/focus")
async def focus_destination(destination_id: str, request: Request) -> dict:
    result = await _service(request).focus_destination(destination_id)
    if result.result == "REJECTED":
        raise HTTPException(status_code=404, detail=result.error or "Unknown destination")
    return result.model_dump(mode="json")


@router.post("/retry")
async def browser_retry(request: Request) -> dict:
    status = await _service(request).retry()
    return status.model_dump(mode="json")
