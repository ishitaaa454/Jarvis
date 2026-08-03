"""
Offline wake-phrase listener using Vosk.

Loads the Vosk model once, then opens the microphone only while listening
for the wake phrase. The stream is always closed before returning so the
clap detector can reclaim the mic safely.

The small English model often mishears "jarvis" as unrelated words when left
unconstrained. We therefore:
  1. Constrain decoding with a phrase grammar (wake variants + [unk])
  2. Keep listening until a match or timeout (ignore early wrong finals)
  3. Apply normalized / fuzzy matching that still rejects partial phrases
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
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


# Phrases the grammar recognizer is allowed to emit (plus [unk]).
WAKE_PHRASE_VARIANTS = (
    "wake up jarvis",
    "wake up, jarvis",
    "wakeup jarvis",
)


@dataclass
class WakeListenResult:
    """Outcome of one wake-phrase listening attempt."""

    matched: bool
    text: str
    timed_out: bool


def normalize_speech_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse spaces, normalize 'wakeup'."""
    lowered = text.lower().strip()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
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
    if not normalized:
        return False

    target = normalize_speech_text(wake_phrase)

    # Hard rejects for required non-matches.
    if normalized in {"wake up", "hello jarvis", "open jarvis"}:
        return False
    if normalized.startswith("hello ") or normalized.startswith("open "):
        return False

    if normalized == target:
        return True
    if normalized in {normalize_speech_text(v) for v in WAKE_PHRASE_VARIANTS}:
        return True

    # Token check: need wake + up + jarvis-like (rejects "wake up" alone).
    tokens = normalized.split()
    has_wake = "wake" in tokens or "wakeup" in tokens
    has_up = "up" in tokens or "wakeup" in tokens
    has_jarvis = any(
        tok.startswith("jarvis") or tok in {"jarvis", "jarvi", "jervis", "jarves"}
        for tok in tokens
    )
    if has_wake and has_up and has_jarvis:
        return True

    # High fuzzy similarity only (grammar usually makes this unnecessary).
    ratio = SequenceMatcher(None, normalized, target).ratio()
    return ratio >= 0.82


def build_wake_grammar(wake_phrase: str = config.WAKE_PHRASE) -> str:
    """JSON grammar list so Vosk prefers the wake phrase over free dictation."""
    phrases = list(WAKE_PHRASE_VARIANTS)
    canonical = normalize_speech_text(wake_phrase)
    if canonical and canonical not in phrases:
        phrases.insert(0, canonical)
    phrases.append("[unk]")
    return json.dumps(phrases)


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
        self._grammar = build_wake_grammar(wake_phrase)

        SetLogLevel(-1)
        resolved = validate_vosk_model_path(model_path)
        logger.info("Loading Vosk model from %s", resolved)
        try:
            self._model = Model(str(resolved))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed to load Vosk model at {resolved}: {exc}") from exc
        logger.info("Vosk model loaded (grammar=%s).", self._grammar)

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

        if start_delay > 0:
            time.sleep(start_delay)

        # Grammar biases decoding toward the wake phrase instead of free text
        # like "the cubs" / "pick up service".
        recognizer = KaldiRecognizer(self._model, self.sample_rate, self._grammar)
        recognizer.SetWords(False)

        last_text = ""
        last_non_unk = ""
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
                    if not text or text == "[unk]":
                        continue

                    last_text = text
                    last_non_unk = text
                    matched = is_wake_phrase(text, self.wake_phrase)
                    logger.info("Wake final hypothesis: %r matched=%s", text, matched)
                    if matched:
                        return WakeListenResult(matched=True, text=text, timed_out=False)
                    # Wrong / partial phrase — keep listening until timeout.
                    continue

                partial = json.loads(recognizer.PartialResult())
                partial_text = (partial.get("partial") or "").strip()
                if partial_text and partial_text != "[unk]":
                    last_text = partial_text
                    if is_wake_phrase(partial_text, self.wake_phrase):
                        # Strong partial match of the full phrase — accept early.
                        logger.info("Wake partial match: %r", partial_text)
                        return WakeListenResult(
                            matched=True,
                            text=partial_text,
                            timed_out=False,
                        )

            payload = json.loads(recognizer.FinalResult())
            text = (payload.get("text") or "").strip()
            if text == "[unk]":
                text = ""
            text = text or last_non_unk or last_text

            if text and is_wake_phrase(text, self.wake_phrase):
                logger.info("Wake timeout match: %r", text)
                return WakeListenResult(matched=True, text=text, timed_out=False)

            if text:
                logger.info("Wake timeout with unmatched text: %r", text)
                return WakeListenResult(matched=False, text=text, timed_out=True)

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
