"""FastAPI application entrypoint for Jarvis Workspace."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import health, tts, voice, websocket
from app.api import system_monitor as system_monitor_api
from app.api import workspace as workspace_api
from app.api.websocket import ConnectionManager, register_websocket_broadcasts
from app.core.config import get_settings
from app.core.events import EventBus
from app.core.logging_config import setup_logging
from app.core.state_manager import StateManager
from app.models.assistant_state import AssistantState
from app.services.assistant import ActivationCoordinator
from app.services.placeholders.integration_service import IntegrationService
from app.services.system_monitor import SystemMonitorService
from app.services.system_service import SystemService
from app.services.tts import TtsService
from app.services.voice import VoiceService
from app.services.workspace import WorkspaceService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handle graceful startup and shutdown state transitions."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Backend startup: %s v%s", settings.app_name, settings.app_version)

    try:
        import psutil

        psutil.cpu_percent(interval=None)
    except Exception:
        logger.exception("Failed to warm CPU sampler")

    if getattr(app.state, "state_broadcast_handler", None) is None:
        handlers = await register_websocket_broadcasts(
            app.state.event_bus,
            app.state.connection_manager,
        )
        app.state.state_broadcast_handler = handlers

    state_manager: StateManager = app.state.state_manager
    voice_service: VoiceService = app.state.voice_service
    tts_service: TtsService = app.state.tts_service
    workspace_service: WorkspaceService = app.state.workspace_service
    system_monitor: SystemMonitorService = app.state.system_monitor_service
    coordinator: ActivationCoordinator = app.state.activation_coordinator

    voice_service.bind(state_manager=state_manager, event_bus=app.state.event_bus)
    tts_service.bind(event_bus=app.state.event_bus)
    workspace_service.bind(event_bus=app.state.event_bus)
    system_monitor.bind(app.state.event_bus)
    coordinator.bind(
        state_manager=state_manager,
        event_bus=app.state.event_bus,
        voice_service=voice_service,
        tts_service=tts_service,
        workspace_service=workspace_service,
    )

    await state_manager.set_state(AssistantState.STARTING)
    await state_manager.set_state(AssistantState.IDLE)
    logger.info("Backend ready (state=IDLE)")

    try:
        await tts_service.on_startup()
    except Exception:
        logger.exception("TTS service startup failed — continuing without speech")

    try:
        await voice_service.on_startup()
    except Exception:
        logger.exception("Voice service startup failed — continuing without listener")

    try:
        await workspace_service.on_startup()
    except Exception:
        logger.exception("Workspace service startup failed — continuing without workspace launch")

    try:
        await system_monitor.on_startup()
    except Exception:
        logger.exception("System monitor startup failed — continuing without monitoring")

    try:
        await coordinator.start()
    except Exception:
        logger.exception("ActivationCoordinator failed to start")

    yield

    logger.info("Backend shutdown requested")
    try:
        await coordinator.stop()
    except Exception:
        logger.exception("ActivationCoordinator shutdown failed")

    try:
        await system_monitor.shutdown()
    except Exception:
        logger.exception("System monitor shutdown failed")

    try:
        await workspace_service.cancel()
    except Exception:
        logger.exception("Workspace service cancellation failed")

    try:
        await tts_service.shutdown()
    except Exception:
        logger.exception("TTS service shutdown failed")

    try:
        await voice_service.shutdown()
    except Exception:
        logger.exception("Voice service shutdown failed")

    try:
        await state_manager.set_state(AssistantState.SHUTTING_DOWN)
    except Exception:
        logger.exception("Failed to set SHUTTING_DOWN state")
    logger.info("Backend shutdown complete")


def create_app() -> FastAPI:
    """Application factory used by Uvicorn and tests."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    event_bus = EventBus()
    state_manager = StateManager(event_bus)
    connection_manager = ConnectionManager()
    voice_service = VoiceService(settings=settings)
    tts_service = TtsService(settings=settings, event_bus=event_bus)
    workspace_service = WorkspaceService(settings=settings, event_bus=event_bus)
    system_monitor = SystemMonitorService(settings=settings, event_bus=event_bus)
    coordinator = ActivationCoordinator(settings=settings)

    app.state.event_bus = event_bus
    app.state.state_manager = state_manager
    app.state.connection_manager = connection_manager
    app.state.system_service = SystemService()
    app.state.system_monitor_service = system_monitor
    app.state.voice_service = voice_service
    app.state.tts_service = tts_service
    app.state.activation_coordinator = coordinator
    app.state.workspace_service = workspace_service
    app.state.integration_service = IntegrationService()
    app.state.state_broadcast_handler = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(voice.router)
    app.include_router(tts.router)
    app.include_router(workspace_api.router)
    app.include_router(system_monitor_api.router)
    app.include_router(websocket.router)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        logger.warning(
            "HTTP error %s on %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": True, "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "detail": "Request validation failed",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "detail": "An unexpected server error occurred.",
            },
        )

    return app


app = create_app()
