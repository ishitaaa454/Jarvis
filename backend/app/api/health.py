"""Health and assistant-state HTTP endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import get_settings
from app.core.state_manager import InvalidStateError
from app.utils.time_utils import utc_iso

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def health_check(request: Request) -> dict[str, Any]:
    """Return service status and live basic system metrics."""
    settings = get_settings()
    system_service = request.app.state.system_service
    metrics = system_service.get_basic_metrics()

    return {
        "status": "online",
        "service": "jarvis-backend",
        "version": settings.app_version,
        "timestamp": utc_iso(),
        "system": metrics,
    }


@router.get("/state")
async def get_state(request: Request) -> dict[str, Any]:
    """Return the current assistant state snapshot."""
    snapshot = request.app.state.state_manager.get_snapshot()
    return {
        "state": snapshot.state.value,
        "previous_state": (
            snapshot.previous_state.value if snapshot.previous_state else None
        ),
        "changed_at": snapshot.changed_at.isoformat(),
    }


@router.post("/state/{new_state}")
async def set_state(new_state: str, request: Request) -> dict[str, Any]:
    """Development-only helper to force a state transition."""
    state_manager = request.app.state.state_manager
    try:
        snapshot = await state_manager.set_state(new_state)
    except InvalidStateError as exc:
        logger.warning("Rejected invalid state transition: %s", new_state)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "state": snapshot.state.value,
        "previous_state": (
            snapshot.previous_state.value if snapshot.previous_state else None
        ),
        "changed_at": snapshot.changed_at.isoformat(),
    }
