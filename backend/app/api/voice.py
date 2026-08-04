"""Voice / wake-phrase HTTP API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.config import get_settings
from app.models.voice import DeviceSelectRequest, VoiceStatusResponse
from app.services.voice.audio_devices import AudioDeviceError
from app.services.voice.voice_service import VoiceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


def _voice_service(request: Request) -> VoiceService:
    return request.app.state.voice_service


@router.get("/status", response_model=VoiceStatusResponse)
async def get_voice_status(request: Request) -> VoiceStatusResponse:
    return _voice_service(request).get_status()


@router.get("/devices")
async def list_voice_devices(request: Request) -> dict:
    service = _voice_service(request)
    try:
        devices = service.list_devices()
    except AudioDeviceError as exc:
        raise HTTPException(status_code=503, detail=exc.user_message) from exc
    return {"devices": [device.model_dump() for device in devices]}


@router.post("/start", response_model=VoiceStatusResponse)
async def start_voice_listener(request: Request) -> VoiceStatusResponse:
    return await _voice_service(request).start()


@router.post("/stop", response_model=VoiceStatusResponse)
async def stop_voice_listener(request: Request) -> VoiceStatusResponse:
    return await _voice_service(request).stop()


@router.put("/device", response_model=VoiceStatusResponse)
async def select_voice_device(
    body: DeviceSelectRequest,
    request: Request,
) -> VoiceStatusResponse:
    service = _voice_service(request)
    try:
        return await service.set_device(body.device_id)
    except AudioDeviceError as exc:
        raise HTTPException(status_code=400, detail=exc.user_message) from exc


@router.post("/test-activation", response_model=VoiceStatusResponse)
async def test_voice_activation(request: Request) -> VoiceStatusResponse:
    """Simulate a wake event. Available only when ENVIRONMENT=development."""
    settings = get_settings()
    if not settings.is_development():
        raise HTTPException(
            status_code=404,
            detail="Test activation is only available in development.",
        )
    logger.info("Development test wake activation requested")
    return await _voice_service(request).simulate_wake()
