"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def backend_root() -> Path:
    """Return the backend package root (directory containing app/)."""
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the Jarvis Workspace backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Jarvis Workspace"
    app_version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8765
    frontend_origin: str = "http://localhost:5173"
    log_level: str = "INFO"
    environment: str = "development"

    # Phase 2 — offline wake-phrase voice service
    voice_enabled: bool = True
    voice_start_automatically: bool = True
    wake_phrase: str = "Wake up Jarvis"
    vosk_model_path: str = "models/vosk-model-small-en-us"
    voice_device_id: int | None = None
    voice_device_name: str = ""
    voice_sample_rate: int = 16000
    voice_block_size: int = 4000
    voice_audio_queue_size: int = 50
    wake_confidence_threshold: float = 0.65
    wake_cooldown_seconds: float = 4.0
    voice_debug_transcripts: bool = False
    voice_activation_display_ms: int = Field(default=1000, ge=800, le=1200)

    @field_validator("voice_device_id", mode="before")
    @classmethod
    def blank_device_id_as_none(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return value

    @field_validator("wake_confidence_threshold")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("WAKE_CONFIDENCE_THRESHOLD must be between 0 and 1")
        return value

    @field_validator("voice_sample_rate")
    @classmethod
    def validate_sample_rate(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("VOICE_SAMPLE_RATE must be positive")
        return value

    @field_validator("voice_block_size", "voice_audio_queue_size")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be a positive integer")
        return value

    @field_validator("wake_cooldown_seconds")
    @classmethod
    def validate_cooldown(cls, value: float) -> float:
        if value < 0:
            raise ValueError("WAKE_COOLDOWN_SECONDS must be >= 0")
        return value

    @model_validator(mode="after")
    def normalize_environment(self) -> Settings:
        self.environment = self.environment.strip().lower()
        return self

    def resolved_vosk_model_path(self) -> Path:
        """Resolve VOSK_MODEL_PATH relative to the backend root when not absolute."""
        path = Path(self.vosk_model_path)
        if not path.is_absolute():
            path = backend_root() / path
        return path.resolve()

    def public_model_path(self) -> str:
        """Return a frontend-safe relative model path (no absolute user dirs)."""
        return self.vosk_model_path.replace("\\", "/")

    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
