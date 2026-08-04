"""Simplified blocking WAV playback suitable for asyncio.to_thread."""

from __future__ import annotations

import logging
import threading
import time
import wave
from pathlib import Path
from typing import Callable

import numpy as np

from app.models.tts import SynthesizedAudio

logger = logging.getLogger(__name__)


class AudioPlayerError(Exception):
    def __init__(self, message: str, *, code: str = "PLAYBACK_ERROR") -> None:
        super().__init__(message)
        self.code = code
        self.user_message = message


class AudioPlayer:
    """Play one utterance at a time; cancelable; run via ``asyncio.to_thread``."""

    def __init__(
        self,
        *,
        volume: float = 0.9,
        play_fn: Callable[..., None] | None = None,
    ) -> None:
        self.volume = max(0.0, min(1.0, volume))
        self._play_fn = play_fn
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._playing = False

    @property
    def is_playing(self) -> bool:
        return self._playing

    def cancel(self) -> None:
        self._cancel.set()

    def reset_cancel(self) -> None:
        self._cancel.clear()

    def play(
        self,
        audio: SynthesizedAudio,
        *,
        device_id: int | None = None,
    ) -> None:
        with self._lock:
            if self._playing:
                raise AudioPlayerError(
                    "Another utterance is already playing.",
                    code="ALREADY_PLAYING",
                )
            self._playing = True
            self._cancel.clear()

        try:
            samples, sample_rate = self._load_wav(audio)
            if self._cancel.is_set():
                return
            samples = np.clip(samples * self.volume, -1.0, 1.0)
            if self._play_fn is not None:
                self._play_fn(samples, sample_rate, device_id, self._cancel)
                return
            self._play_sounddevice(samples, sample_rate, device_id)
        finally:
            self._playing = False

    def _play_sounddevice(
        self,
        samples: np.ndarray,
        sample_rate: int,
        device_id: int | None,
    ) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioPlayerError(
                "sounddevice is not installed.",
                code="SOUNDDEVICE_MISSING",
            ) from exc

        try:
            sd.play(samples, samplerate=sample_rate, device=device_id, blocking=False)
            duration = float(len(samples)) / float(sample_rate)
            elapsed = 0.0
            step = 0.05
            while elapsed < duration + 0.15:
                if self._cancel.is_set():
                    sd.stop()
                    return
                time.sleep(step)
                elapsed += step
            sd.wait()
        except Exception as exc:
            try:
                import sounddevice as sd

                sd.stop()
            except Exception:
                pass
            raise AudioPlayerError(
                f"Unable to play audio on the selected output device: {exc}",
                code="PLAYBACK_FAILED",
            ) from exc

    @staticmethod
    def _load_wav(audio: SynthesizedAudio) -> tuple[np.ndarray, int]:
        if not audio.path:
            raise AudioPlayerError("No audio path provided.", code="INVALID_WAV")
        path = Path(audio.path)
        if not path.exists():
            raise AudioPlayerError("Audio file is missing.", code="INVALID_WAV")
        try:
            with wave.open(str(path), "rb") as wav:
                channels = wav.getnchannels()
                width = wav.getsampwidth()
                rate = wav.getframerate()
                frames = wav.readframes(wav.getnframes())
        except wave.Error as exc:
            raise AudioPlayerError("WAV file is corrupted.", code="INVALID_WAV") from exc

        if channels < 1 or width not in {1, 2} or rate < 1 or not frames:
            raise AudioPlayerError("Unsupported WAV format.", code="INVALID_WAV")

        if width == 2:
            data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            data = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0

        if channels > 1:
            data = data.reshape(-1, channels).mean(axis=1)

        return data.astype(np.float32), rate
