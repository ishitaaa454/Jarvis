"""WebSocket connection management and /ws endpoint."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import STATE_CHANGED, EventBus
from app.core.state_manager import StateManager
from app.models.websocket_message import WebSocketMessage

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


def create_state_change_handler(
    manager: ConnectionManager,
) -> Any:
    """Build an event-bus handler that broadcasts state changes."""

    async def _on_state_changed(payload: dict[str, Any]) -> None:
        message = WebSocketMessage(type="state.changed", payload=payload)
        await manager.broadcast(message.to_dict())

    return _on_state_changed


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Accept a dashboard client and stream connection + state events."""
    app = websocket.app
    manager: ConnectionManager = app.state.connection_manager
    state_manager: StateManager = app.state.state_manager

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

    # Keep the connection open; state broadcasts are delivered via EventBus.
    try:
        while True:
            # Phase 1 does not process client commands; drain inbound frames.
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
) -> Any:
    """Subscribe the connection manager to state-change events."""
    handler = create_state_change_handler(manager)
    await event_bus.subscribe(STATE_CHANGED, handler)
    return handler
