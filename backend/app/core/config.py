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

    # Phase 3 — offline Piper TTS
    tts_enabled: bool = True
    tts_start_automatically: bool = True
    piper_executable_path: str = ""
    piper_voice_model_path: str = (
        "voices/en_GB-alan-medium/en_GB-alan-medium.onnx"
    )
    piper_voice_config_path: str = (
        "voices/en_GB-alan-medium/en_GB-alan-medium.onnx.json"
    )
    tts_output_device_id: int | None = None
    tts_output_device_name: str = ""
    tts_volume: float = 0.90
    tts_length_scale: float = 1.08
    tts_noise_scale: float = 0.667
    tts_noise_width: float = 0.80
    welcome_line_1: str = "Welcome back, Ishita. Initializing your workspace."
    welcome_line_2: str = "All systems are online."
    welcome_line_3: str = "Opening your workspace now."
    welcome_sentence_pause_ms: int = Field(default=700, ge=0, le=5000)
    tts_pre_speech_delay_ms: int = Field(default=200, ge=0, le=5000)
    tts_post_speech_delay_ms: int = Field(default=700, ge=0, le=5000)
    tts_synthesis_timeout_seconds: float = Field(default=30.0, gt=0)
    tts_queue_size: int = Field(default=5, ge=1, le=50)
    tts_temp_directory: str = ""
    tts_delete_temp_audio: bool = True

    @field_validator("voice_device_id", "tts_output_device_id", mode="before")
    @classmethod
    def blank_device_id_as_none(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return value

    @field_validator("wake_confidence_threshold", "tts_volume")
    @classmethod
    def validate_unit_interval(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("must be between 0 and 1")
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

    @field_validator("tts_length_scale", "tts_noise_scale", "tts_noise_width")
    @classmethod
    def validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @model_validator(mode="after")
    def normalize_environment(self) -> Settings:
        self.environment = self.environment.strip().lower()
        return self

    def resolve_path(self, path: str) -> Path:
        p = Path(path)
        if not path:
            return backend_root()
        if not p.is_absolute():
            p = backend_root() / p
        return p.resolve()

    def resolved_vosk_model_path(self) -> Path:
        return self.resolve_path(self.vosk_model_path)

    def public_model_path(self) -> str:
        return self.vosk_model_path.replace("\\", "/")

    def resolved_piper_executable(self) -> Path | None:
        if not self.piper_executable_path.strip():
            return None
        return self.resolve_path(self.piper_executable_path)

    def resolved_piper_model_path(self) -> Path:
        return self.resolve_path(self.piper_voice_model_path)

    def resolved_piper_config_path(self) -> Path:
        return self.resolve_path(self.piper_voice_config_path)

    def resolved_tts_temp_dir(self) -> Path:
        if self.tts_temp_directory.strip():
            return self.resolve_path(self.tts_temp_directory)
        return (backend_root() / "tmp" / "tts").resolve()

    def public_piper_model_path(self) -> str:
        return self.piper_voice_model_path.replace("\\", "/")

    def welcome_lines(self) -> list[str]:
        return [self.welcome_line_1, self.welcome_line_2, self.welcome_line_3]

    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
