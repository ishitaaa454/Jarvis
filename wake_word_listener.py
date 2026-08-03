"""
Offline wake-phrase listener using Vosk.

Loads the Vosk model once, then opens the microphone only while listening
for the wake phrase. The stream is always closed before returning so the
clap detector can reclaim the mic safely.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger("jarvis.wake")

try:
    import sounddevice as sd
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Missing dependency 'sounddevice'. Install with: pip install -r requirements.txt"
    ) from exc

try:
    from vosk import KaldiRecognizer, Model, SetLogLevel
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Missing dependency 'vosk'. Install with: pip install -r requirements.txt"
    ) from exc


@dataclass
class WakeListenResult:
    """Outcome of one wake-phrase listening attempt."""

    matched: bool
    text: str
    timed_out: bool


def normalize_speech_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse spaces, normalize 'wakeup'."""
    lowered = text.lower().strip()
    # Remove punctuation (keep letters, digits, spaces).
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # "Wakeup Jarvis" -> "wake up jarvis"
    cleaned = re.sub(r"\bwakeup\b", "wake up", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def is_wake_phrase(text: str, wake_phrase: str = config.WAKE_PHRASE) -> bool:
    """
    Return True only for the full wake phrase (and close variants).

    Accepts: "wake up jarvis", "wake up, jarvis", "wakeup jarvis"
    Rejects: "hello jarvis", "open jarvis", "wake up"
    """
    normalized = normalize_speech_text(text)
    target = normalize_speech_text(wake_phrase)
    # Exact match after normalization — prevents partial phrases like "wake up".
    return normalized == target


def validate_vosk_model_path(model_path: str | Path) -> Path:
    """Ensure the Vosk model directory exists and looks valid."""
    path = Path(model_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path

    if not path.exists():
        raise FileNotFoundError(
            f"Vosk model not found at: {path}\n"
            "Download vosk-model-small-en-us-0.15 and extract it under models/.\n"
            "See models/README.md for exact steps."
        )

    if not path.is_dir():
        raise NotADirectoryError(
            f"VOSK_MODEL_PATH is not a directory: {path}\n"
            "Point config.VOSK_MODEL_PATH at the extracted model folder."
        )

    # A real Vosk model contains these subfolders.
    required = ("am", "conf", "graph")
    missing = [name for name in required if not (path / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Invalid Vosk model at {path} (missing: {', '.join(missing)}).\n"
            "Make sure you extracted the full model archive, not just the zip file."
        )

    return path


class WakeWordListener:
    """Reusable offline wake-phrase listener (Vosk model loaded once)."""

    def __init__(
        self,
        model_path: str = config.VOSK_MODEL_PATH,
        sample_rate: int = config.SPEECH_SAMPLE_RATE,
        block_size: int = config.SPEECH_BLOCK_SIZE,
        wake_phrase: str = config.WAKE_PHRASE,
        listen_timeout: float = config.WAKE_LISTEN_TIMEOUT,
        start_delay: float = config.WAKE_START_DELAY,
    ) -> None:
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.wake_phrase = wake_phrase
        self.listen_timeout = listen_timeout
        self.start_delay = start_delay

        SetLogLevel(-1)  # Keep Vosk quiet in the console.
        resolved = validate_vosk_model_path(model_path)
        logger.info("Loading Vosk model from %s", resolved)
        try:
            self._model = Model(str(resolved))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed to load Vosk model at {resolved}: {exc}") from exc
        logger.info("Vosk model loaded.")

        self._stream: Optional[sd.RawInputStream] = None

    def listen_for_wake_phrase(
        self,
        timeout: Optional[float] = None,
        start_delay: Optional[float] = None,
    ) -> WakeListenResult:
        """
        Open the mic, listen up to timeout seconds, then close the mic.

        Call this only after the clap detector has released the microphone.
        """
        timeout = self.listen_timeout if timeout is None else timeout
        start_delay = self.start_delay if start_delay is None else start_delay

        # Brief pause so the clap transient is not fed into the recognizer.
        if start_delay > 0:
            time.sleep(start_delay)

        recognizer = KaldiRecognizer(self._model, self.sample_rate)
        recognizer.SetWords(False)

        last_text = ""
        deadline = time.monotonic() + timeout

        try:
            # Exclusive mic use for speech — clap stream must already be stopped.
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=1,
                dtype="int16",
            )
            self._stream.start()
        except PermissionError as exc:
            logger.exception("Microphone permission denied during wake listen.")
            raise PermissionError(
                "Microphone permission denied. Allow mic access in "
                "Windows Settings > Privacy & security > Microphone."
            ) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Audio stream failure during wake listen.")
            raise RuntimeError(f"Audio stream failure during wake listen: {exc}") from exc

        try:
            while time.monotonic() < deadline:
                try:
                    data, overflowed = self._stream.read(self.block_size)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Wake-phrase audio read failed.")
                    raise RuntimeError(f"Audio stream error while listening: {exc}") from exc

                if overflowed:
                    logger.warning("Wake-phrase audio overflow.")

                raw = bytes(data)
                if recognizer.AcceptWaveform(raw):
                    payload = json.loads(recognizer.Result())
                    text = (payload.get("text") or "").strip()
                    if text:
                        last_text = text
                        matched = is_wake_phrase(text, self.wake_phrase)
                        logger.info("Wake final hypothesis: %r matched=%s", text, matched)
                        return WakeListenResult(matched=matched, text=text, timed_out=False)
                else:
                    partial = json.loads(recognizer.PartialResult())
                    partial_text = (partial.get("partial") or "").strip()
                    if partial_text:
                        last_text = partial_text

            # Timeout — flush any remaining hypothesis.
            payload = json.loads(recognizer.FinalResult())
            text = (payload.get("text") or "").strip() or last_text
            if text:
                matched = is_wake_phrase(text, self.wake_phrase)
                logger.info(
                    "Wake timeout with text: %r matched=%s",
                    text,
                    matched,
                )
                return WakeListenResult(matched=matched, text=text, timed_out=not matched)

            logger.info("Wake phrase timeout with no recognized speech.")
            return WakeListenResult(matched=False, text="", timed_out=True)
        finally:
            self._close_stream()

    def close(self) -> None:
        """Release any open stream (model stays loaded for reuse)."""
        self._close_stream()

    def _close_stream(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error closing wake-phrase audio stream: %s", exc)
        self._stream = None
