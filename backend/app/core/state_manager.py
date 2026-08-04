"""Central assistant state manager with async-safe transitions and event publish."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.core.events import STATE_CHANGED, EventBus
from app.models.assistant_state import AssistantState, AssistantStateSnapshot
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)


class InvalidStateError(ValueError):
    """Raised when a requested state value is not a valid AssistantState."""


class StateManager:
    """Owns the single source of truth for assistant lifecycle state.

    Designed for FastAPI: one instance is stored on app.state and shared by
    HTTP and WebSocket handlers. Transitions are guarded by an asyncio lock.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._lock = asyncio.Lock()
        self._state: AssistantState = AssistantState.OFFLINE
        self._previous_state: Optional[AssistantState] = None
        self._changed_at = utc_now()

    @property
    def current_state(self) -> AssistantState:
        return self._state

    def get_snapshot(self) -> AssistantStateSnapshot:
        """Return a read-only snapshot of the current state."""
        return AssistantStateSnapshot(
            state=self._state,
            previous_state=self._previous_state,
            changed_at=self._changed_at,
        )

    def parse_state(self, value: str) -> AssistantState:
        """Validate and parse a state string into AssistantState."""
        normalized = value.strip().upper()
        try:
            return AssistantState(normalized)
        except ValueError as exc:
            valid = ", ".join(s.value for s in AssistantState)
            raise InvalidStateError(
                f"Invalid state '{value}'. Valid states: {valid}"
            ) from exc

    async def set_state(self, new_state: AssistantState | str) -> AssistantStateSnapshot:
        """Transition to a new state and notify subscribers."""
        if isinstance(new_state, str):
            new_state = self.parse_state(new_state)

        async with self._lock:
            if new_state == self._state:
                return self.get_snapshot()

            previous = self._state
            self._previous_state = previous
            self._state = new_state
            self._changed_at = utc_now()
            snapshot = self.get_snapshot()

        logger.info("State changed: %s -> %s", previous.value, new_state.value)

        await self._event_bus.publish(
            STATE_CHANGED,
            {
                "state": snapshot.state.value,
                "previous_state": (
                    snapshot.previous_state.value if snapshot.previous_state else None
                ),
                "changed_at": snapshot.changed_at.isoformat(),
            },
        )
        return snapshot
