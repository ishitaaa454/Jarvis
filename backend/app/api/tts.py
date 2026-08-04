"""TTS / welcome-sequence HTTP API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.config import get_settings
from app.models.tts import OutputDeviceSelectRequest, TtsStatusResponse
from app.services.assistant.activation_coordinator import ActivationCoordinator
from app.services.tts.audio_output_devices import AudioOutputError
from app.services.tts.piper_engine import PiperEngineError
from app.services.tts.tts_service import SequenceBusyError, TtsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts", tags=["tts"])


def _tts(request: Request) -> TtsService:
    return request.app.state.tts_service


def _coordinator(request: Request) -> ActivationCoordinator:
    return request.app.state.activation_coordinator


@router.get("/status", response_model=TtsStatusResponse)
async def get_tts_status(request: Request) -> TtsStatusResponse:
    return _tts(request).get_status()


@router.get("/devices")
async def list_tts_devices(request: Request) -> dict:
    try:
        devices = _tts(request).list_devices()
    except AudioOutputError as exc:
        raise HTTPException(status_code=503, detail=exc.user_message) from exc
    return {"devices": [d.model_dump() for d in devices]}


@router.put("/device", response_model=TtsStatusResponse)
async def select_tts_device(
    body: OutputDeviceSelectRequest,
    request: Request,
) -> TtsStatusResponse:
    try:
        return await _tts(request).set_device(body.device_id)
    except AudioOutputError as exc:
        raise HTTPException(status_code=400, detail=exc.user_message) from exc


@router.post("/test-welcome", response_model=TtsStatusResponse)
async def test_welcome_sequence(request: Request) -> TtsStatusResponse:
    settings = get_settings()
    if not settings.is_development():
        raise HTTPException(
            status_code=404,
            detail="Test welcome is only available in development.",
        )
    coordinator = _coordinator(request)
    try:
        await coordinator.run_test_welcome()
    except SequenceBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PiperEngineError as exc:
        raise HTTPException(status_code=503, detail=exc.user_message) from exc
    return _tts(request).get_status()


@router.post("/cancel", response_model=TtsStatusResponse)
async def cancel_speech(request: Request) -> TtsStatusResponse:
    await _coordinator(request).cancel()
    return _tts(request).get_status()


@router.post("/retry", response_model=TtsStatusResponse)
async def retry_tts(request: Request) -> TtsStatusResponse:
    return await _tts(request).retry_validation()
