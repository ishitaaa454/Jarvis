"""WebSocket connection management and /ws endpoint."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import (
    STATE_CHANGED,
    VOICE_ERROR,
    VOICE_STATUS_CHANGED,
    VOICE_WAKE_DETECTED,
    EventBus,
)
from app.core.state_manager import StateManager
from app.models.voice import voice_status_to_ws_payload
from app.models.websocket_message import WebSocketMessage
from app.services.voice.voice_service import VoiceService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Tracks active WebSocket clients and broadcasts events to them."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info("WebSocket connected (%d clients)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("WebSocket disconnected (%d clients)", len(self._connections))

    async def send_json(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        await websocket.send_json(data)

    async def broadcast(self, data: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._connections)

        stale: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json(data)
            except Exception:
                logger.exception("Failed to send WebSocket message; marking stale")
                stale.append(websocket)

        for websocket in stale:
            await self.disconnect(websocket)


def create_state_change_handler(manager: ConnectionManager) -> Any:
    """Build an event-bus handler that broadcasts state changes."""

    async def _on_state_changed(payload: dict[str, Any]) -> None:
        message = WebSocketMessage(type="state.changed", payload=payload)
        await manager.broadcast(message.to_dict())

    return _on_state_changed


def create_voice_event_handlers(manager: ConnectionManager) -> list[tuple[str, Any]]:
    """Handlers that mirror voice EventBus events onto WebSocket clients."""

    async def _on_voice_status(payload: dict[str, Any]) -> None:
        message = WebSocketMessage(type=VOICE_STATUS_CHANGED, payload=payload)
        await manager.broadcast(message.to_dict())

    async def _on_wake(payload: dict[str, Any]) -> None:
        # Never include raw audio in wake events
        safe = {
            "phrase": payload.get("phrase"),
            "confidence": payload.get("confidence"),
        }
        message = WebSocketMessage(type=VOICE_WAKE_DETECTED, payload=safe)
        await manager.broadcast(message.to_dict())

    async def _on_voice_error(payload: dict[str, Any]) -> None:
        message = WebSocketMessage(type=VOICE_ERROR, payload=payload)
        await manager.broadcast(message.to_dict())

    return [
        (VOICE_STATUS_CHANGED, _on_voice_status),
        (VOICE_WAKE_DETECTED, _on_wake),
        (VOICE_ERROR, _on_voice_error),
    ]


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Accept a dashboard client and stream connection, state, and voice events."""
    app = websocket.app
    manager: ConnectionManager = app.state.connection_manager
    state_manager: StateManager = app.state.state_manager
    voice_service: VoiceService = app.state.voice_service

    await manager.connect(websocket)

    established = WebSocketMessage(
        type="connection.established",
        payload={"message": "Connected to Jarvis backend"},
    )
    await manager.send_json(websocket, established.to_dict())

    snapshot = state_manager.get_snapshot()
    state_message = WebSocketMessage(
        type="state.changed",
        payload={
            "state": snapshot.state.value,
            "previous_state": (
                snapshot.previous_state.value if snapshot.previous_state else None
            ),
            "changed_at": snapshot.changed_at.isoformat(),
        },
    )
    await manager.send_json(websocket, state_message.to_dict())

    voice_message = WebSocketMessage(
        type=VOICE_STATUS_CHANGED,
        payload=voice_status_to_ws_payload(voice_service.get_status()),
    )
    await manager.send_json(websocket, voice_message.to_dict())

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WebSocket client closed connection")
    except Exception:
        logger.exception("Unexpected WebSocket error")
    finally:
        await manager.disconnect(websocket)


async def register_websocket_broadcasts(
    event_bus: EventBus,
    manager: ConnectionManager,
) -> list[Any]:
    """Subscribe the connection manager to state and voice events."""
    handlers: list[Any] = []
    state_handler = create_state_change_handler(manager)
    await event_bus.subscribe(STATE_CHANGED, state_handler)
    handlers.append(state_handler)

    for event_type, handler in create_voice_event_handlers(manager):
        await event_bus.subscribe(event_type, handler)
        handlers.append(handler)

    return handlers
