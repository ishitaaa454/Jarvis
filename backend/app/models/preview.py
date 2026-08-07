"""Phase 7 window preview models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class PreviewMode(str, Enum):
    OFF = "OFF"
    BLURRED = "BLURRED"
    VISIBLE = "VISIBLE"


class PreviewResult(BaseModel):
    window_id: str
    available: bool
    reason: str | None = None
    content_type: str = "image/jpeg"
    width: int | None = None
    height: int | None = None
    captured_at: datetime | None = None
    # Bytes stay backend-only; API streams them separately.
