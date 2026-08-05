"""Workspace-launching HTTP API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.config import get_settings
from app.models.application import ApplicationActionResult, WorkspaceStatusResponse
from app.services.workspace.workspace_service import (
    WorkspaceRunConflictError,
    WorkspaceService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


def _workspace(request: Request) -> WorkspaceService:
    return request.app.state.workspace_service


@router.get("/status", response_model=WorkspaceStatusResponse)
async def get_workspace_status(request: Request) -> WorkspaceStatusResponse:
    return _workspace(request).get_status()


@router.get("/applications")
async def list_workspace_applications(request: Request) -> dict:
    apps = _workspace(request).list_applications()
    return {"applications": [app.model_dump() for app in apps]}


@router.post("/start", response_model=WorkspaceStatusResponse)
async def start_workspace(request: Request) -> WorkspaceStatusResponse:
    settings = get_settings()
    if not (settings.is_development() or settings.workspace_manual_start_in_production):
        raise HTTPException(
            status_code=404,
            detail="Manual workspace start is only available in development.",
        )
    try:
        return await _workspace(request).start_default_workspace()
    except WorkspaceRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/cancel", response_model=WorkspaceStatusResponse)
async def cancel_workspace(request: Request) -> WorkspaceStatusResponse:
    return await _workspace(request).cancel()


@router.post("/applications/{app_id}/open", response_model=ApplicationActionResult)
async def open_workspace_application(app_id: str, request: Request) -> ApplicationActionResult:
    try:
        return await _workspace(request).open_application(app_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown application id: {app_id}") from exc


@router.post("/applications/{app_id}/focus", response_model=ApplicationActionResult)
async def focus_workspace_application(app_id: str, request: Request) -> ApplicationActionResult:
    try:
        return await _workspace(request).focus_application(app_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown application id: {app_id}") from exc


@router.post("/refresh", response_model=WorkspaceStatusResponse)
async def refresh_workspace(request: Request) -> WorkspaceStatusResponse:
    return _workspace(request).refresh()
