"""Placeholder voice service for later phases.

Future responsibility:
- Wake-phrase detection ("Wake up, Jarvis.")
- Speech recognition
- Text-to-speech with a deep British male voice
- Spoken welcome / status lines

Phase 1 intentionally does not implement audio capture, Whisper, Piper,
or any TTS engine.
"""

from __future__ import annotations


class VoiceService:
    """Scaffold for wake-word, STT, and TTS integration."""

    def start_listening(self) -> None:
        """Begin continuous wake-phrase monitoring."""
        raise NotImplementedError("Voice listening will be implemented in a later phase.")

    def stop_listening(self) -> None:
        """Stop wake-phrase monitoring."""
        raise NotImplementedError("Voice listening will be implemented in a later phase.")

    def speak(self, text: str) -> None:
        """Speak the given text using the configured voice profile."""
        raise NotImplementedError(
            f"Text-to-speech is not available in Phase 1 (text={text!r})."
        )
