"""Tests for wake-phrase normalization, matching, confidence, and cooldown."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.voice.wake_phrase_detector import (
    WakePhraseDetector,
    average_word_confidence,
    is_wake_phrase,
    normalize_wake_text,
    validate_vosk_model_dir,
    VoskModelMissingError,
)


@pytest.fixture
def detector(tmp_path: Path) -> WakePhraseDetector:
    # Inject a dummy model object so ensure_model_loaded is not required for text tests
    return WakePhraseDetector(
        tmp_path / "missing-model",
        wake_phrase="Wake up Jarvis",
        confidence_threshold=0.65,
        cooldown_seconds=4.0,
        model=object(),
    )


def test_normalize_lowercase_and_punctuation() -> None:
    assert normalize_wake_text("Wake up, Jarvis.") == "wake up jarvis"
    assert normalize_wake_text("WAKE UP JARVIS") == "wake up jarvis"
    assert normalize_wake_text("  wake   up  jarvis  ") == "wake up jarvis"


def test_normalize_wakeup_token() -> None:
    assert normalize_wake_text("wakeup jarvis") == "wake up jarvis"
    assert normalize_wake_text("Wakeup, Jarvis!") == "wake up jarvis"


def test_exact_phrase_match_variants() -> None:
    assert is_wake_phrase(normalize_wake_text("Wake up Jarvis"))
    assert is_wake_phrase(normalize_wake_text("Wake up, Jarvis"))
    assert is_wake_phrase(normalize_wake_text("WAKE UP JARVIS"))
    assert is_wake_phrase(normalize_wake_text("wake up jarvis"))
    assert is_wake_phrase(normalize_wake_text("wakeup jarvis"))


def test_partial_and_unrelated_rejection() -> None:
    rejects = [
        "jarvis",
        "hello jarvis",
        "open jarvis",
        "wake up",
        "wake jarvis",
        "wake up iris",
        "hey jarvis",
        "the weather today",
        "background television jarvis",
    ]
    for text in rejects:
        assert not is_wake_phrase(normalize_wake_text(text)), text


def test_average_word_confidence() -> None:
    result = {
        "text": "wake up jarvis",
        "result": [
            {"word": "wake", "conf": 0.9},
            {"word": "up", "conf": 0.8},
            {"word": "jarvis", "conf": 0.7},
        ],
    }
    assert average_word_confidence(result) == pytest.approx(0.8)


def test_average_word_confidence_missing() -> None:
    assert average_word_confidence({"text": "wake up jarvis"}) is None
    assert average_word_confidence({"text": "x", "result": []}) is None


def test_confidence_threshold_blocks(detector: WakePhraseDetector) -> None:
    outcome = detector.evaluate_recognized_text("wake up jarvis", confidence=0.2)
    assert not outcome.activated
    assert outcome.rejected_reason == "low_confidence"


def test_confidence_threshold_allows(detector: WakePhraseDetector) -> None:
    outcome = detector.evaluate_recognized_text("wake up jarvis", confidence=0.91)
    assert outcome.activated
    assert outcome.phrase == "wake up jarvis"
    assert outcome.confidence == pytest.approx(0.91)


def test_missing_word_confidence_defaults_to_one(detector: WakePhraseDetector) -> None:
    outcome = detector.evaluate_recognized_text(
        "wake up jarvis",
        raw_result={"text": "wake up jarvis"},
    )
    assert outcome.activated
    assert outcome.confidence == pytest.approx(1.0)


def test_cooldown_prevents_duplicate(detector: WakePhraseDetector) -> None:
    first = detector.evaluate_recognized_text("wake up jarvis", confidence=0.9, now=100.0)
    assert first.activated
    second = detector.evaluate_recognized_text("wake up jarvis", confidence=0.9, now=101.0)
    assert not second.activated
    assert second.rejected_reason == "cooldown"


def test_activation_after_cooldown(detector: WakePhraseDetector) -> None:
    first = detector.evaluate_recognized_text("wake up jarvis", confidence=0.9, now=100.0)
    assert first.activated
    again = detector.evaluate_recognized_text("wake up jarvis", confidence=0.9, now=105.0)
    assert again.activated


def test_hello_jarvis_rejected(detector: WakePhraseDetector) -> None:
    outcome = detector.evaluate_recognized_text("hello jarvis", confidence=0.99)
    assert not outcome.activated
    assert outcome.rejected_reason == "phrase_mismatch"


def test_validate_missing_model(tmp_path: Path) -> None:
    with pytest.raises(VoskModelMissingError):
        validate_vosk_model_dir(tmp_path / "nope")


def test_validate_incomplete_model(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    (model / "am").mkdir()
    with pytest.raises(VoskModelMissingError):
        validate_vosk_model_dir(model)
