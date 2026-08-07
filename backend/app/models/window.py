"""Phase 7 window inventory and switcher models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class WindowTitleMode(str, Enum):
    SAFE = "SAFE"
    FULL = "FULL"
    HIDDEN = "HIDDEN"


class FocusResultCode(str, Enum):
    FOCUSED = "FOCUSED"
    RESTORED = "RESTORED"
    RUNNING_FOCUS_LIMITED = "RUNNING_FOCUS_LIMITED"
    WINDOW_NOT_FOUND = "WINDOW_NOT_FOUND"
    APPLICATION_NOT_RUNNING = "APPLICATION_NOT_RUNNING"
    ACCESS_LIMITED = "ACCESS_LIMITED"
    FAILED = "FAILED"


class SafeWindowRecord(BaseModel):
    window_id: str
    application_id: str
    process_id: int | None = None
    display_title: str
    visible: bool = True
    minimized: bool = False
    foreground: bool = False
    focusable: bool = True
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_jarvis_focus_at: datetime | None = None


class ApplicationWindowGroup(BaseModel):
    application_id: str
    display_name: str
    running: bool = False
    window_count: int = 0
    foreground: bool = False
    favourite: bool = False
    allow_preview: bool = False
    windows: list[SafeWindowRecord] = Field(default_factory=list)


class WindowInventorySnapshot(BaseModel):
    applications: list[ApplicationWindowGroup] = Field(default_factory=list)
    total_windows: int = 0
    running_applications: int = 0
    foreground_application_id: str | None = None
    foreground_window_id: str | None = None
    collected_at: datetime | None = None
    available: bool = True
    reason: str | None = None


class RecentWindowRecord(BaseModel):
    window_id: str
    application_id: str
    display_name: str
    display_title: str
    last_foreground_at: datetime


class WindowFocusResult(BaseModel):
    application_id: str
    window_id: str
    result: FocusResultCode
    restored: bool = False
    foreground: bool = False
    focus_limited: bool = False
    error: str | None = None


class PreviewAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    DISABLED = "DISABLED"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"
    WINDOW_NOT_FOUND = "WINDOW_NOT_FOUND"
