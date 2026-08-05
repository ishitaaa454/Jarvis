"""Backward-compatible re-export.

Phase 4 implements the real workspace-launching service under
``app.services.workspace``. This module is kept so any existing imports of
``app.services.placeholders.workspace_service.WorkspaceService`` keep working.
"""

from __future__ import annotations

from app.services.workspace.workspace_service import (
    WorkspaceRunConflictError,
    WorkspaceService,
)

__all__ = ["WorkspaceService", "WorkspaceRunConflictError"]
