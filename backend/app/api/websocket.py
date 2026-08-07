"""WebSocket connection management and /ws endpoint."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import (
    ASSISTANT_ACTIVATION_FINISHED,
    ASSISTANT_ACTIVATION_STARTED,
    ASSISTANT_WORKSPACE_INITIALIZATION_STARTED,
    ASSISTANT_WORKSPACE_READY,
    STATE_CHANGED,
    SYSTEM_CAPABILITIES_CHANGED,
    SYSTEM_METRICS,
    SYSTEM_MONITOR_ERROR,
    SYSTEM_MONITOR_STATUS,
    SYSTEM_MONITOR_WARNING,
    SYSTEM_PROCESSES_UPDATED,
    TTS_ERROR,
    TTS_SEQUENCE_CANCELLED,
    TTS_SEQUENCE_FINISHED,
    TTS_SEQUENCE_STARTED,
    TTS_STATUS_CHANGED,
    TTS_UTTERANCE_FINISHED,
    TTS_UTTERANCE_STARTED,
    VOICE_ERROR,
    VOICE_STATUS_CHANGED,
    VOICE_WAKE_DETECTED,
    WORKSPACE_APPLICATION_RESULT,
    WORKSPACE_APPLICATION_STATUS,
    WORKSPACE_ERROR,
    WORKSPACE_RUN_CANCELLED,
    WORKSPACE_RUN_FINISHED,
    WORKSPACE_RUN_STARTED,
    WORKSPACE_STATUS_CHANGED,
    WORKSPACE_WARNING,
    EventBus,
)
from app.core.state_manager import StateManager
from app.models.application import workspace_status_to_ws_payload
from app.models.tts import tts_status_to_ws_payload
from app.models.voice import voice_status_to_ws_payload
from app.models.websocket_message import WebSocketMessage
from app.services.system_monitor.system_monitor_service import SystemMonitorService
from app.services.tts.tts_service import TtsService
from app.services.voice.voice_service import VoiceService
from app.services.workspace.workspace_service import WorkspaceService

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
    async def _on_state_changed(payload: dict[str, Any]) -> None:
        message = WebSocketMessage(type="state.changed", payload=payload)
        await manager.broadcast(message.to_dict())

    return _on_state_changed


def _mirror(manager: ConnectionManager, event_type: str) -> Any:
    async def _handler(payload: dict[str, Any]) -> None:
        # Never include raw audio fields
        safe = {k: v for k, v in payload.items() if k not in {"audio", "pcm", "wav", "samples"}}
        message = WebSocketMessage(type=event_type, payload=safe)
        await manager.broadcast(message.to_dict())

    return _handler


def create_voice_event_handlers(manager: ConnectionManager) -> list[tuple[str, Any]]:
    return [
        (VOICE_STATUS_CHANGED, _mirror(manager, VOICE_STATUS_CHANGED)),
        (VOICE_WAKE_DETECTED, _mirror(manager, VOICE_WAKE_DETECTED)),
        (VOICE_ERROR, _mirror(manager, VOICE_ERROR)),
    ]


def create_tts_event_handlers(manager: ConnectionManager) -> list[tuple[str, Any]]:
    return [
        (TTS_STATUS_CHANGED, _mirror(manager, TTS_STATUS_CHANGED)),
        (TTS_SEQUENCE_STARTED, _mirror(manager, TTS_SEQUENCE_STARTED)),
        (TTS_UTTERANCE_STARTED, _mirror(manager, TTS_UTTERANCE_STARTED)),
        (TTS_UTTERANCE_FINISHED, _mirror(manager, TTS_UTTERANCE_FINISHED)),
        (TTS_SEQUENCE_FINISHED, _mirror(manager, TTS_SEQUENCE_FINISHED)),
        (TTS_SEQUENCE_CANCELLED, _mirror(manager, TTS_SEQUENCE_CANCELLED)),
        (TTS_ERROR, _mirror(manager, TTS_ERROR)),
        (ASSISTANT_ACTIVATION_STARTED, _mirror(manager, ASSISTANT_ACTIVATION_STARTED)),
        (ASSISTANT_ACTIVATION_FINISHED, _mirror(manager, ASSISTANT_ACTIVATION_FINISHED)),
    ]


def create_workspace_event_handlers(manager: ConnectionManager) -> list[tuple[str, Any]]:
    return [
        (WORKSPACE_STATUS_CHANGED, _mirror(manager, WORKSPACE_STATUS_CHANGED)),
        (WORKSPACE_RUN_STARTED, _mirror(manager, WORKSPACE_RUN_STARTED)),
        (WORKSPACE_APPLICATION_STATUS, _mirror(manager, WORKSPACE_APPLICATION_STATUS)),
        (WORKSPACE_APPLICATION_RESULT, _mirror(manager, WORKSPACE_APPLICATION_RESULT)),
        (WORKSPACE_RUN_FINISHED, _mirror(manager, WORKSPACE_RUN_FINISHED)),
        (WORKSPACE_RUN_CANCELLED, _mirror(manager, WORKSPACE_RUN_CANCELLED)),
        (WORKSPACE_WARNING, _mirror(manager, WORKSPACE_WARNING)),
        (WORKSPACE_ERROR, _mirror(manager, WORKSPACE_ERROR)),
        (
            ASSISTANT_WORKSPACE_INITIALIZATION_STARTED,
            _mirror(manager, ASSISTANT_WORKSPACE_INITIALIZATION_STARTED),
        ),
        (ASSISTANT_WORKSPACE_READY, _mirror(manager, ASSISTANT_WORKSPACE_READY)),
    ]


def create_system_monitor_event_handlers(manager: ConnectionManager) -> list[tuple[str, Any]]:
    return [
        (SYSTEM_MONITOR_STATUS, _mirror(manager, SYSTEM_MONITOR_STATUS)),
        (SYSTEM_METRICS, _mirror(manager, SYSTEM_METRICS)),
        (SYSTEM_PROCESSES_UPDATED, _mirror(manager, SYSTEM_PROCESSES_UPDATED)),
        (SYSTEM_CAPABILITIES_CHANGED, _mirror(manager, SYSTEM_CAPABILITIES_CHANGED)),
        (SYSTEM_MONITOR_WARNING, _mirror(manager, SYSTEM_MONITOR_WARNING)),
        (SYSTEM_MONITOR_ERROR, _mirror(manager, SYSTEM_MONITOR_ERROR)),
    ]


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Accept a dashboard client and stream connection, state, voice, and TTS events."""
    app = websocket.app
    manager: ConnectionManager = app.state.connection_manager
    state_manager: StateManager = app.state.state_manager
    voice_service: VoiceService = app.state.voice_service
    tts_service: TtsService = app.state.tts_service
    workspace_service: WorkspaceService = app.state.workspace_service
    system_monitor: SystemMonitorService = app.state.system_monitor_service

    await manager.connect(websocket)

    established = WebSocketMessage(
        type="connection.established",
        payload={"message": "Connected to Jarvis backend"},
    )
    await manager.send_json(websocket, established.to_dict())

    snapshot = state_manager.get_snapshot()
    await manager.send_json(
        websocket,
        WebSocketMessage(
            type="state.changed",
            payload={
                "state": snapshot.state.value,
                "previous_state": (
                    snapshot.previous_state.value if snapshot.previous_state else None
                ),
                "changed_at": snapshot.changed_at.isoformat(),
            },
        ).to_dict(),
    )

    await manager.send_json(
        websocket,
        WebSocketMessage(
            type=VOICE_STATUS_CHANGED,
            payload=voice_status_to_ws_payload(voice_service.get_status()),
        ).to_dict(),
    )

    await manager.send_json(
        websocket,
        WebSocketMessage(
            type=TTS_STATUS_CHANGED,
            payload=tts_status_to_ws_payload(tts_service.get_status()),
        ).to_dict(),
    )

    await manager.send_json(
        websocket,
        WebSocketMessage(
            type=WORKSPACE_STATUS_CHANGED,
            payload=workspace_status_to_ws_payload(workspace_service.get_status()),
        ).to_dict(),
    )

    await manager.send_json(
        websocket,
        WebSocketMessage(
            type=SYSTEM_MONITOR_STATUS,
            payload=system_monitor.get_status().model_dump(mode="json"),
        ).to_dict(),
    )
    await manager.send_json(
        websocket,
        WebSocketMessage(
            type=SYSTEM_METRICS,
            payload={
                "cpu": system_monitor.get_snapshot().cpu.model_dump(mode="json"),
                "memory": system_monitor.get_snapshot().memory.model_dump(mode="json"),
                "disk_activity": system_monitor.get_snapshot().disks.activity.model_dump(
                    mode="json"
                ),
                "network": {
                    **system_monitor.get_snapshot().network.model_dump(mode="json"),
                    "adapters": [],
                },
                "battery": system_monitor.get_snapshot().battery.model_dump(mode="json"),
                "gpu": system_monitor.get_snapshot().gpu.model_dump(mode="json"),
                "temperatures": system_monitor.get_snapshot().temperatures.model_dump(
                    mode="json"
                ),
            },
        ).to_dict(),
    )

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
    handlers: list[Any] = []
    state_handler = create_state_change_handler(manager)
    await event_bus.subscribe(STATE_CHANGED, state_handler)
    handlers.append(state_handler)

    for event_type, handler in create_voice_event_handlers(manager):
        await event_bus.subscribe(event_type, handler)
        handlers.append(handler)

    for event_type, handler in create_tts_event_handlers(manager):
        await event_bus.subscribe(event_type, handler)
        handlers.append(handler)

    for event_type, handler in create_workspace_event_handlers(manager):
        await event_bus.subscribe(event_type, handler)
        handlers.append(handler)

    for event_type, handler in create_system_monitor_event_handlers(manager):
        await event_bus.subscribe(event_type, handler)
        handlers.append(handler)

    return handlers
