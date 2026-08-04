"""FastAPI application entrypoint for Jarvis Workspace Phase 1."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import health, websocket
from app.api.websocket import ConnectionManager, register_websocket_broadcasts
from app.core.config import get_settings
from app.core.events import EventBus
from app.core.logging_config import setup_logging
from app.core.state_manager import StateManager
from app.models.assistant_state import AssistantState
from app.services.placeholders.integration_service import IntegrationService
from app.services.placeholders.voice_service import VoiceService
from app.services.placeholders.workspace_service import WorkspaceService
from app.services.system_service import SystemService

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
        handler = await register_websocket_broadcasts(
            app.state.event_bus,
            app.state.connection_manager,
        )
        app.state.state_broadcast_handler = handler

    state_manager: StateManager = app.state.state_manager
    await state_manager.set_state(AssistantState.STARTING)
    await state_manager.set_state(AssistantState.IDLE)
    logger.info("Backend ready (state=IDLE)")

    yield

    logger.info("Backend shutdown requested")
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

    app.state.event_bus = event_bus
    app.state.state_manager = state_manager
    app.state.connection_manager = connection_manager
    app.state.system_service = SystemService()
    app.state.voice_service = VoiceService()
    app.state.workspace_service = WorkspaceService()
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
