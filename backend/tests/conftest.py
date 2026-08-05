"""Shared pytest fixtures for Jarvis backend tests.

Hardware, Vosk models, Piper, speakers, and automatic listener/TTS startup
are disabled by default so the suite runs offline without a microphone.
"""

from __future__ import annotations

import os

import pytest

# Ensure settings are deterministic before app imports resolve get_settings().
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("VOICE_ENABLED", "true")
os.environ.setdefault("VOICE_START_AUTOMATICALLY", "false")
os.environ.setdefault("VOSK_MODEL_PATH", "models/vosk-model-small-en-us")
os.environ.setdefault("TTS_ENABLED", "true")
os.environ.setdefault("TTS_START_AUTOMATICALLY", "false")
os.environ.setdefault("WORKSPACE_ENABLED", "true")
os.environ.setdefault("WORKSPACE_START_AFTER_WELCOME", "false")


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
