"""Lightweight in-process event bus for state and connection notifications."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], Awaitable[None] | None]


class EventBus:
    """Async-safe publish/subscribe bus used by StateManager and WebSocket layer."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        async with self._lock:
            self._subscribers.setdefault(event_type, []).append(handler)

    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        async with self._lock:
            handlers = self._subscribers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            handlers = list(self._subscribers.get(event_type, []))

        for handler in handlers:
            try:
                result = handler(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("Event handler failed for '%s'", event_type)


STATE_CHANGED = "state.changed"
CLIENT_CONNECTED = "client.connected"
CLIENT_DISCONNECTED = "client.disconnected"
