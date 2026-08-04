"""Voice-service status and device models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VoiceServiceStatus(str, Enum):
    """Lifecycle states for the wake-phrase voice service (not assistant states)."""

    DISABLED = "DISABLED"
    STARTING = "STARTING"
    LOADING_MODEL = "LOADING_MODEL"
    LISTENING = "LISTENING"
    ACTIVATION_DETECTED = "ACTIVATION_DETECTED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    MODEL_MISSING = "MODEL_MISSING"
    ERROR = "ERROR"


class AudioDeviceInfo(BaseModel):
    """Clean description of a microphone input device."""

    id: int
    name: str
    host_api: str
    max_input_channels: int
    default_sample_rate: float
    is_default: bool = False


class MicrophoneStatus(BaseModel):
    """Subset of device info returned in voice status payloads."""

    id: int | None = None
    name: str | None = None
    is_default: bool = False


class VoiceStatusResponse(BaseModel):
    """Public voice-service status for HTTP and WebSocket clients."""

    enabled: bool
    status: VoiceServiceStatus
    wake_phrase: str
    model_loaded: bool
    model_path: str
    microphone: MicrophoneStatus | None = None
    last_activation_at: datetime | None = None
    last_error: str | None = None


class DeviceSelectRequest(BaseModel):
    """Request body for selecting an input device."""

    device_id: int = Field(..., ge=0)


class WakeDetectionResult(BaseModel):
    """Internal result produced when the wake phrase is confirmed."""

    phrase: str
    confidence: float
    raw_text: str = ""


def voice_status_to_ws_payload(status: VoiceStatusResponse) -> dict[str, Any]:
    """Compact payload for voice.status_changed WebSocket events."""
    mic_name = status.microphone.name if status.microphone else None
    return {
        "status": status.status.value,
        "microphone_name": mic_name,
        "enabled": status.enabled,
        "model_loaded": status.model_loaded,
        "wake_phrase": status.wake_phrase,
        "last_error": status.last_error,
        "last_activation_at": (
            status.last_activation_at.isoformat() if status.last_activation_at else None
        ),
    }
