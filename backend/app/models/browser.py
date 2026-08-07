"""Phase 7 browser integration models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class BrowserIntegrationStatus(str, Enum):
    DISABLED = "DISABLED"
    UNAVAILABLE = "UNAVAILABLE"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class BrowserIntegrationMode(str, Enum):
    SESSION = "session"
    CDP = "cdp"


class BrowserDestinationDefinition(BaseModel):
    id: str
    display_name: str
    url: str
    allowed_hosts: list[str] = Field(default_factory=list)


class BrowserDestinationStatus(BaseModel):
    id: str
    display_name: str
    known_open: bool = False
    exact_focus_available: bool = False
    url: str | None = None
    last_opened_at: datetime | None = None
    last_focused_at: datetime | None = None


class BrowserStatusResponse(BaseModel):
    enabled: bool
    status: BrowserIntegrationStatus
    mode: BrowserIntegrationMode
    cdp_enabled: bool = False
    exact_tab_focus_available: bool = False
    reason: str | None = None


class BrowserActionResult(BaseModel):
    destination_id: str
    action: str
    result: str
    exact_focus: bool = False
    error: str | None = None
