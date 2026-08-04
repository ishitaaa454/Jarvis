"""Offline wake-phrase detection helpers and Vosk recognizer wrapper.

Confidence calculation (documented):
    When Vosk returns a final result with per-word ``conf`` values, confidence is
    the arithmetic mean of those word confidences for the recognized utterance.
    If the normalized text exactly matches the wake phrase but word confidences
    are absent (some builds omit them), confidence defaults to 1.0 so a clear
    grammar match is not rejected arbitrarily. Activation requires
    confidence >= configured threshold. Partial phrases never activate.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

CANONICAL_WAKE_PHRASE = "wake up jarvis"

# Restricted grammar keeps recognition focused on the wake phrase.
WAKE_PHRASE_GRAMMAR = json.dumps(
    [
        "wake up jarvis",
        "wake up",
        "jarvis",
        "wake",
        "up",
        "[unk]",
    ]
)


class VoskModelMissingError(Exception):
    """Raised when the configured Vosk model directory is missing or invalid."""

    def __init__(self, path: Path, message: str | None = None) -> None:
        self.path = path
        super().__init__(message or f"Vosk model not found at {path}")


class RecognizerFactory(Protocol):
    """Creates a Vosk recognizer for a sample rate (injectable for tests)."""

    def create(self, sample_rate: int) -> Any: ...


@dataclass
class DetectionOutcome:
    """Result of feeding audio or text into the detector."""

    activated: bool
    phrase: str | None = None
    confidence: float = 0.0
    raw_text: str = ""
    rejected_reason: str | None = None


def normalize_wake_text(text: str) -> str:
    """Normalize recognized text for exact wake-phrase comparison."""
    lowered = text.lower()
    # Remove punctuation (keep alphanumerics and spaces)
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Vosk sometimes emits "wakeup" as one token
    cleaned = re.sub(r"\bwakeup\b", "wake up", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def is_wake_phrase(normalized: str, expected: str = CANONICAL_WAKE_PHRASE) -> bool:
    """Return True only when the complete normalized phrase matches."""
    return normalized == normalize_wake_text(expected)


def average_word_confidence(result: dict[str, Any]) -> float | None:
    """Compute mean per-word confidence from a Vosk final result dict.

    Returns None when word-level confidences are unavailable.
    """
    words = result.get("result")
    if not isinstance(words, list) or not words:
        return None
    confidences: list[float] = []
    for item in words:
        if not isinstance(item, dict):
            continue
        if "conf" not in item:
            continue
        try:
            confidences.append(float(item["conf"]))
        except (TypeError, ValueError):
            continue
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def validate_vosk_model_dir(model_path: Path) -> None:
    """Ensure the path looks like an extracted Vosk model directory."""
    if not model_path.exists():
        raise VoskModelMissingError(model_path, f"Vosk model path does not exist: {model_path}")
    if not model_path.is_dir():
        raise VoskModelMissingError(model_path, f"Vosk model path is not a directory: {model_path}")

    expected_markers = ("am", "conf", "graph")
    missing = [name for name in expected_markers if not (model_path / name).exists()]
    if missing:
        raise VoskModelMissingError(
            model_path,
            f"Vosk model directory is incomplete (missing: {', '.join(missing)}): {model_path}",
        )


class WakePhraseDetector:
    """Loads Vosk once and confirms the exact wake phrase from PCM audio or text."""

    def __init__(
        self,
        model_path: Path,
        *,
        wake_phrase: str = "Wake up Jarvis",
        confidence_threshold: float = 0.65,
        cooldown_seconds: float = 4.0,
        debug_transcripts: bool = False,
        recognizer_factory: RecognizerFactory | None = None,
        model: Any | None = None,
    ) -> None:
        self.model_path = model_path
        self.wake_phrase = wake_phrase
        self.confidence_threshold = confidence_threshold
        self.cooldown_seconds = cooldown_seconds
        self.debug_transcripts = debug_transcripts
        self._recognizer_factory = recognizer_factory
        self._model = model
        self._recognizer: Any | None = None
        self._sample_rate: int | None = None
        self._last_activation_monotonic: float | None = None
        self._model_load_attempted = False
        self._model_load_error: str | None = None

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    @property
    def last_model_error(self) -> str | None:
        return self._model_load_error

    def ensure_model_loaded(self) -> None:
        """Load the Vosk model once. Subsequent calls are no-ops after success or hard miss."""
        if self._model is not None:
            return
        if self._model_load_attempted and self._model_load_error:
            # Avoid hammering a missing path every second
            raise VoskModelMissingError(self.model_path, self._model_load_error)

        self._model_load_attempted = True
        try:
            validate_vosk_model_dir(self.model_path)
            if self._recognizer_factory is None:
                from vosk import Model

                self._model = Model(str(self.model_path))
            else:
                # Factory-only mode still requires a valid path unless a model was injected
                if self._model is None:
                    # Tests inject factory without a real Model object
                    self._model = object()
            self._model_load_error = None
            logger.info("Vosk model loaded from %s", self.model_path)
        except VoskModelMissingError as exc:
            self._model_load_error = str(exc)
            logger.error("Vosk model missing/invalid: %s", exc)
            raise
        except ImportError as exc:
            self._model_load_error = "vosk is not installed"
            logger.error("vosk package is not installed")
            raise VoskModelMissingError(self.model_path, "vosk is not installed") from exc
        except Exception as exc:
            self._model_load_error = f"Failed to load Vosk model: {exc}"
            logger.exception("Failed to load Vosk model from %s", self.model_path)
            raise VoskModelMissingError(self.model_path, self._model_load_error) from exc

    def prepare_recognizer(self, sample_rate: int) -> None:
        """Create or reset the recognizer for the given sample rate."""
        self.ensure_model_loaded()
        if self._recognizer is not None and self._sample_rate == sample_rate:
            return

        if self._recognizer_factory is not None:
            self._recognizer = self._recognizer_factory.create(sample_rate)
        else:
            from vosk import KaldiRecognizer

            recognizer = KaldiRecognizer(self._model, sample_rate, WAKE_PHRASE_GRAMMAR)
            recognizer.SetWords(True)
            self._recognizer = recognizer

        self._sample_rate = sample_rate

    def release(self) -> None:
        """Drop the recognizer (model may remain loaded)."""
        self._recognizer = None
        self._sample_rate = None

    def reset_cooldown(self) -> None:
        self._last_activation_monotonic = None

    def evaluate_recognized_text(
        self,
        text: str,
        *,
        confidence: float | None = None,
        raw_result: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> DetectionOutcome:
        """Pure matching path used by tests and the recognition worker."""
        normalized = normalize_wake_text(text)
        if self.debug_transcripts and normalized:
            logger.info("[VOICE_DEBUG_TRANSCRIPT] recognized=%r normalized=%r", text, normalized)

        if not normalized:
            return DetectionOutcome(activated=False, raw_text=text)

        if not is_wake_phrase(normalized, self.wake_phrase):
            return DetectionOutcome(
                activated=False,
                raw_text=text,
                rejected_reason="phrase_mismatch",
            )

        if confidence is None and raw_result is not None:
            confidence = average_word_confidence(raw_result)
        if confidence is None:
            # Exact phrase match without word confidences — treat as full confidence.
            confidence = 1.0

        if confidence < self.confidence_threshold:
            logger.info(
                "Wake phrase matched but confidence %.3f below threshold %.3f",
                confidence,
                self.confidence_threshold,
            )
            return DetectionOutcome(
                activated=False,
                phrase=normalized,
                confidence=confidence,
                raw_text=text,
                rejected_reason="low_confidence",
            )

        monotonic_now = time.monotonic() if now is None else now
        if self._last_activation_monotonic is not None:
            elapsed = monotonic_now - self._last_activation_monotonic
            if elapsed < self.cooldown_seconds:
                logger.info(
                    "Wake phrase rejected by cooldown (%.2fs remaining)",
                    self.cooldown_seconds - elapsed,
                )
                return DetectionOutcome(
                    activated=False,
                    phrase=normalized,
                    confidence=confidence,
                    raw_text=text,
                    rejected_reason="cooldown",
                )

        self._last_activation_monotonic = monotonic_now
        return DetectionOutcome(
            activated=True,
            phrase=normalized,
            confidence=confidence,
            raw_text=text,
        )

    def process_audio(self, pcm16_mono: bytes) -> DetectionOutcome | None:
        """Feed PCM16 mono bytes into Vosk. Returns an outcome on final results only."""
        if self._recognizer is None:
            raise RuntimeError("Recognizer not prepared; call prepare_recognizer first")

        if self._recognizer.AcceptWaveform(pcm16_mono):
            raw = self._recognizer.Result()
            return self._handle_final_result(raw)

        # Partial results are intentionally not published / logged (unless debug).
        if self.debug_transcripts:
            try:
                partial = json.loads(self._recognizer.PartialResult())
                partial_text = str(partial.get("partial", "") or "")
                if partial_text:
                    logger.info("[VOICE_DEBUG_TRANSCRIPT] partial=%r", partial_text)
            except Exception:
                pass
        return None

    def flush(self) -> DetectionOutcome | None:
        """Flush any pending recognition result."""
        if self._recognizer is None:
            return None
        raw = self._recognizer.FinalResult()
        return self._handle_final_result(raw)

    def _handle_final_result(self, raw_json: str) -> DetectionOutcome:
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            return DetectionOutcome(activated=False, raw_text=raw_json)

        text = str(payload.get("text", "") or "")
        return self.evaluate_recognized_text(text, raw_result=payload)
