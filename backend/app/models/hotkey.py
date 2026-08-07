"""Phase 7 global hotkey models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class HotkeyServiceStatus(str, Enum):
    DISABLED = "DISABLED"
    STARTING = "STARTING"
    REGISTERED = "REGISTERED"
    CONFLICT = "CONFLICT"
    ERROR = "ERROR"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


class HotkeyAction(str, Enum):
    SHOW_DASHBOARD = "SHOW_DASHBOARD"


class HotkeyShortcut(BaseModel):
    action: HotkeyAction
    display: str


class HotkeyStatusResponse(BaseModel):
    enabled: bool
    status: HotkeyServiceStatus
    shortcuts: list[HotkeyShortcut] = Field(default_factory=list)
    last_triggered_at: datetime | None = None
    conflict_message: str | None = None
