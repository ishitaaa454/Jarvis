"""Assistant state models and enums."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.utils.time_utils import utc_now


class AssistantState(str, Enum):
    """Supported assistant lifecycle states for Phase 1 and beyond."""

    OFFLINE = "OFFLINE"
    STARTING = "STARTING"
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    INITIALIZING_WORKSPACE = "INITIALIZING_WORKSPACE"
    OPENING_APPLICATIONS = "OPENING_APPLICATIONS"
    READY = "READY"
    ERROR = "ERROR"
    SHUTTING_DOWN = "SHUTTING_DOWN"


class AssistantStateSnapshot(BaseModel):
    """Serializable snapshot of the current assistant state."""

    state: AssistantState
    previous_state: Optional[AssistantState] = None
    changed_at: datetime = Field(default_factory=utc_now)
