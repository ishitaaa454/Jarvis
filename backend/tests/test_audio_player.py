"""AudioPlayer unit tests with play_fn fakes — no real speakers."""

from __future__ import annotations

import threading
import time
import wave
from pathlib import Path

import pytest

from app.models.tts import SynthesizedAudio
from app.services.tts.audio_player import AudioPlayer, AudioPlayerError


def _write_silent_wav(path: Path, *, duration: float = 0.1, rate: int = 22050) -> None:
    frames = int(rate * duration)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * frames)


def _audio(path: Path) -> SynthesizedAudio:
    return SynthesizedAudio(
        path=str(path),
        sample_rate=22050,
        channels=1,
        sample_width=2,
        duration_seconds=0.1,
        text="test",
    )


def test_play_invokes_play_fn(tmp_path: Path) -> None:
    wav_path = tmp_path / "utt.wav"
    _write_silent_wav(wav_path)
    calls: list[tuple] = []

    def play_fn(samples, sample_rate, device_id, cancel_event) -> None:
        calls.append((len(samples), sample_rate, device_id, cancel_event.is_set()))

    player = AudioPlayer(volume=0.5, play_fn=play_fn)
    assert player.is_playing is False
    player.play(_audio(wav_path), device_id=3)
    assert len(calls) == 1
    assert calls[0][1] == 22050
    assert calls[0][2] == 3
    assert calls[0][3] is False
    assert player.is_playing is False


def test_cancel_stops_play_fn(tmp_path: Path) -> None:
    wav_path = tmp_path / "utt.wav"
    _write_silent_wav(wav_path, duration=0.5)
    started = threading.Event()
    saw_cancel = threading.Event()

    def play_fn(samples, sample_rate, device_id, cancel_event) -> None:
        started.set()
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if cancel_event.is_set():
                saw_cancel.set()
                return
            time.sleep(0.01)

    player = AudioPlayer(play_fn=play_fn)
    thread = threading.Thread(
        target=player.play,
        args=(_audio(wav_path),),
        kwargs={"device_id": None},
        daemon=True,
    )
    thread.start()
    assert started.wait(timeout=2.0)
    player.cancel()
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    assert saw_cancel.is_set()
    assert player.is_playing is False


def test_missing_wav_rejected(tmp_path: Path) -> None:
    player = AudioPlayer(play_fn=lambda *a: None)
    audio = SynthesizedAudio(
        path=str(tmp_path / "missing.wav"),
        sample_rate=22050,
        duration_seconds=0.1,
    )
    with pytest.raises(AudioPlayerError) as exc:
        player.play(audio)
    assert exc.value.code == "INVALID_WAV"


def test_concurrent_play_rejected(tmp_path: Path) -> None:
    wav_path = tmp_path / "utt.wav"
    _write_silent_wav(wav_path)
    gate = threading.Event()
    entered = threading.Event()

    def play_fn(samples, sample_rate, device_id, cancel_event) -> None:
        entered.set()
        gate.wait(timeout=2.0)

    player = AudioPlayer(play_fn=play_fn)
    first = threading.Thread(target=player.play, args=(_audio(wav_path),), daemon=True)
    first.start()
    assert entered.wait(timeout=2.0)
    with pytest.raises(AudioPlayerError) as exc:
        player.play(_audio(wav_path))
    assert exc.value.code == "ALREADY_PLAYING"
    gate.set()
    first.join(timeout=2.0)
