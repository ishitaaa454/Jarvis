"""Retired Phase 1 voice placeholder.

The real offline wake-phrase implementation lives in ``app.services.voice``.
This module re-exports ``VoiceService`` so any lingering imports keep working.
"""

from app.services.voice.voice_service import VoiceService

__all__ = ["VoiceService"]
