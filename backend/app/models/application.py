"""Application registry and workspace result models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class LaunchType(str, Enum):
    EXECUTABLE = "executable"
    URL = "url"
    URI = "uri"
    START_APP = "start_app"
    BROWSER_URL = "browser_url"


class ApplicationActionStatus(str, Enum):
    PENDING = "PENDING"
    CHECKING = "CHECKING"
    ALREADY_RUNNING = "ALREADY_RUNNING"
    RESTORING = "RESTORING"
    FOCUSING = "FOCUSING"
    LAUNCHING = "LAUNCHING"
    OPENING_URL = "OPENING_URL"
    OPENING_URI = "OPENING_URI"
    WAITING_FOR_STARTUP = "WAITING_FOR_STARTUP"
    READY = "READY"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkspaceServiceStatus(str, Enum):
    IDLE = "IDLE"
    PREPARING = "PREPARING"
    LAUNCHING = "LAUNCHING"
    CANCELLING = "CANCELLING"
    READY = "READY"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class ApplicationDefinition(BaseModel):
    id: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    display_name: str
    enabled: bool = True
    launch_type: LaunchType
    executable_candidates: list[str] = Field(default_factory=list)
    configured_path: str = ""
    process_names: list[str] = Field(default_factory=list)
    window_title_patterns: list[str] = Field(default_factory=list)
    launch_arguments: list[str] = Field(default_factory=list)
    url: str | None = None
    uri: str | None = None
    start_app_name: str | None = None
    startup_delay_ms: int = Field(default=800, ge=0, le=30000)
    focus_existing: bool = True
    request_focus_on_launch: bool = False
    allow_multiple_instances: bool = False
    order: int = Field(default=100, ge=0)

    @field_validator("launch_arguments")
    @classmethod
    def no_shell_metacharacters(cls, value: list[str]) -> list[str]:
        forbidden = set("&|;`$<>")
        for arg in value:
            if any(ch in forbidden for ch in arg):
                raise ValueError(f"Unsafe launch argument rejected: {arg!r}")
        return value


class ApplicationsConfigFile(BaseModel):
    profile: str = "default"
    applications: list[ApplicationDefinition]

    @model_validator(mode="after")
    def unique_ids(self) -> ApplicationsConfigFile:
        ids = [app.id for app in self.applications]
        if len(ids) != len(set(ids)):
            raise ValueError("Application IDs must be unique")
        return self


class ApplicationActionResult(BaseModel):
    application_id: str
    display_name: str
    requested_action: str
    result: str
    running: bool = False
    window_found: bool = False
    focus_requested: bool = False
    focus_succeeded: bool = False
    process_id: int | None = None
    duration_ms: int = 0
    error: str | None = None
    status: ApplicationActionStatus = ApplicationActionStatus.READY


class WorkspaceRunSummary(BaseModel):
    run_id: str
    status: WorkspaceServiceStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int = 0
    total_applications: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    applications: list[ApplicationActionResult] = Field(default_factory=list)


class WorkspaceProgress(BaseModel):
    completed: int = 0
    total: int = 0


class WorkspaceStatusResponse(BaseModel):
    enabled: bool
    status: WorkspaceServiceStatus
    active_run_id: str | None = None
    profile: str = "default"
    total_configured: int = 0
    total_enabled: int = 0
    current_application: str | None = None
    progress: WorkspaceProgress = Field(default_factory=WorkspaceProgress)
    last_run: WorkspaceRunSummary | None = None
    last_error: str | None = None


class ApplicationRuntimeView(BaseModel):
    id: str
    display_name: str
    enabled: bool
    order: int
    launch_type: LaunchType
    resolved: bool = False
    running: bool = False
    window_found: bool = False
    status: ApplicationActionStatus = ApplicationActionStatus.PENDING
    last_result: str | None = None


def workspace_status_to_ws_payload(status: WorkspaceStatusResponse) -> dict[str, Any]:
    return {
        "status": status.status.value,
        "active_run_id": status.active_run_id,
        "profile": status.profile,
        "total_enabled": status.total_enabled,
        "current_application": status.current_application,
        "progress": status.progress.model_dump(),
        "last_error": status.last_error,
    }
