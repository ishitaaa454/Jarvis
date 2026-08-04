"""TTS / Piper speech-output models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TtsServiceStatus(str, Enum):
    """Lifecycle states for the TTS service (not assistant states)."""

    DISABLED = "DISABLED"
    STARTING = "STARTING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    SYNTHESIZING = "SYNTHESIZING"
    SPEAKING = "SPEAKING"
    CANCELLING = "CANCELLING"
    STOPPED = "STOPPED"
    MODEL_MISSING = "MODEL_MISSING"
    ENGINE_MISSING = "ENGINE_MISSING"
    OUTPUT_UNAVAILABLE = "OUTPUT_UNAVAILABLE"
    ERROR = "ERROR"


class OutputDeviceInfo(BaseModel):
    id: int
    name: str
    host_api: str
    max_output_channels: int
    default_sample_rate: float
    is_default: bool = False


class OutputDeviceStatus(BaseModel):
    id: int | None = None
    name: str | None = None
    is_default: bool = False


class TtsStatusResponse(BaseModel):
    enabled: bool
    status: TtsServiceStatus
    engine: str = "Piper"
    voice: str = "en_GB-alan-medium"
    model_loaded: bool
    output_device: OutputDeviceStatus | None = None
    is_speaking: bool = False
    current_sequence: str | None = None
    current_utterance_index: int | None = None
    last_spoken_at: datetime | None = None
    last_error: str | None = None
    volume: float | None = None
    length_scale: float | None = None
    sentence_pause_ms: int | None = None
    microphone_suppressed: bool = False


class OutputDeviceSelectRequest(BaseModel):
    device_id: int = Field(..., ge=0)


class SynthesizedAudio(BaseModel):
    """Metadata for a synthesized WAV (path optional for in-memory tests)."""

    path: str | None = None
    sample_rate: int
    channels: int = 1
    sample_width: int = 2
    duration_seconds: float = 0.0
    text: str = ""


def tts_status_to_ws_payload(status: TtsStatusResponse) -> dict[str, Any]:
    return {
        "status": status.status.value,
        "engine": status.engine,
        "voice": status.voice,
        "model_loaded": status.model_loaded,
        "is_speaking": status.is_speaking,
        "current_sequence": status.current_sequence,
        "current_utterance_index": status.current_utterance_index,
        "last_error": status.last_error,
        "output_device_name": (
            status.output_device.name if status.output_device else None
        ),
        "microphone_suppressed": status.microphone_suppressed,
        "last_spoken_at": (
            status.last_spoken_at.isoformat() if status.last_spoken_at else None
        ),
    }
