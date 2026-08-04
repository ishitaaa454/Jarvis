"""WebSocket message envelope model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.utils.time_utils import utc_now


class WebSocketMessage(BaseModel):
    """Reusable envelope for all WebSocket events."""

    type: str
    timestamp: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for WebSocket JSON transmission."""
        return {
            "type": self.type,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
        }
