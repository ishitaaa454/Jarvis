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

# Phase 2 voice events
VOICE_STATUS_CHANGED = "voice.status_changed"
VOICE_WAKE_DETECTED = "voice.wake_detected"
VOICE_ERROR = "voice.error"

# Phase 3 TTS events
TTS_STATUS_CHANGED = "tts.status_changed"
TTS_SEQUENCE_STARTED = "tts.sequence_started"
TTS_UTTERANCE_STARTED = "tts.utterance_started"
TTS_UTTERANCE_FINISHED = "tts.utterance_finished"
TTS_SEQUENCE_FINISHED = "tts.sequence_finished"
TTS_SEQUENCE_CANCELLED = "tts.sequence_cancelled"
TTS_ERROR = "tts.error"
ASSISTANT_ACTIVATION_STARTED = "assistant.activation_started"
ASSISTANT_ACTIVATION_FINISHED = "assistant.activation_finished"

# Phase 4 workspace events
WORKSPACE_STATUS_CHANGED = "workspace.status_changed"
WORKSPACE_RUN_STARTED = "workspace.run_started"
WORKSPACE_APPLICATION_STATUS = "workspace.application_status"
WORKSPACE_APPLICATION_RESULT = "workspace.application_result"
WORKSPACE_RUN_FINISHED = "workspace.run_finished"
WORKSPACE_RUN_CANCELLED = "workspace.run_cancelled"
WORKSPACE_WARNING = "workspace.warning"
WORKSPACE_ERROR = "workspace.error"
ASSISTANT_WORKSPACE_INITIALIZATION_STARTED = "assistant.workspace_initialization_started"
ASSISTANT_WORKSPACE_READY = "assistant.workspace_ready"

# Phase 6 system monitoring events
SYSTEM_MONITOR_STATUS = "system.monitor_status"
SYSTEM_METRICS = "system.metrics"
SYSTEM_PROCESSES_UPDATED = "system.processes_updated"
SYSTEM_CAPABILITIES_CHANGED = "system.capabilities_changed"
SYSTEM_MONITOR_WARNING = "system.monitor_warning"
SYSTEM_MONITOR_ERROR = "system.monitor_error"

# Phase 7 — command centre
WINDOWS_INVENTORY_CHANGED = "windows.inventory_changed"
WINDOWS_FOREGROUND_CHANGED = "windows.foreground_changed"
WINDOWS_WINDOW_ADDED = "windows.window_added"
WINDOWS_WINDOW_REMOVED = "windows.window_removed"
WINDOWS_WINDOW_STATE_CHANGED = "windows.window_state_changed"
HOTKEY_STATUS_CHANGED = "hotkey.status_changed"
HOTKEY_TRIGGERED = "hotkey.triggered"
BROWSER_STATUS_CHANGED = "browser.status_changed"
BROWSER_DESTINATION_OPENED = "browser.destination_opened"
BROWSER_DESTINATION_FOCUSED = "browser.destination_focused"
BROWSER_DESTINATION_UNAVAILABLE = "browser.destination_unavailable"
