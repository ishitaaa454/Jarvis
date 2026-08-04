"""TtsService welcome-sequence tests with fake Piper + play_fn."""

from __future__ import annotations

import asyncio
import threading
import time
import wave
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.events import (
    TTS_SEQUENCE_FINISHED,
    TTS_UTTERANCE_STARTED,
    EventBus,
)
from app.models.tts import SynthesizedAudio, TtsServiceStatus
from app.services.tts.audio_output_devices import AudioOutputDeviceManager
from app.services.tts.audio_player import AudioPlayer
from app.services.tts.tts_service import SequenceBusyError, TtsService

WELCOME = [
    "Welcome back, Ishita. Initializing your workspace.",
    "All systems are online.",
    "Opening your workspace now.",
]


def _write_silent_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        wav.writeframes(b"\x00\x00" * 1102)


class FakeEngine:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.texts: list[str] = []
        self._validated = True
        self.stopped = False

    def validate(self) -> None:
        self._validated = True

    def synthesize(self, text: str) -> SynthesizedAudio:
        self.texts.append(text)
        path = self.tmp_path / f"synth-{len(self.texts)}.wav"
        _write_silent_wav(path)
        return SynthesizedAudio(
            path=str(path),
            sample_rate=22050,
            channels=1,
            sample_width=2,
            duration_seconds=0.05,
            text=text,
        )

    def stop(self) -> None:
        self.stopped = True

    def cleanup_cache(self) -> None:
        return None


class FakeSoundDevice:
    def __init__(self) -> None:
        self.default = type("D", (), {"device": (None, 0)})()

    def query_devices(self):
        return [
            {
                "name": "Fake Speakers",
                "hostapi": 0,
                "max_output_channels": 2,
                "default_samplerate": 48000,
            }
        ]

    def query_hostapis(self):
        return [{"name": "Windows WASAPI"}]


@pytest.fixture
def tts_settings(tmp_path: Path) -> Settings:
    return Settings(
        tts_enabled=True,
        tts_start_automatically=False,
        welcome_line_1=WELCOME[0],
        welcome_line_2=WELCOME[1],
        welcome_line_3=WELCOME[2],
        welcome_sentence_pause_ms=10,
        tts_pre_speech_delay_ms=0,
        tts_post_speech_delay_ms=0,
        tts_delete_temp_audio=False,
        tts_temp_directory=str(tmp_path / "tts-tmp"),
        environment="development",
    )


@pytest.fixture
async def tts_bundle(tts_settings: Settings, tmp_path: Path):
    bus = EventBus()
    engine = FakeEngine(tmp_path)
    played: list[str] = []

    def play_fn(samples, sample_rate, device_id, cancel_event) -> None:
        played.append("ok")

    service = TtsService(
        settings=tts_settings,
        event_bus=bus,
        engine=engine,  # type: ignore[arg-type]
        player=AudioPlayer(volume=0.9, play_fn=play_fn),
        device_manager=AudioOutputDeviceManager(sounddevice_module=FakeSoundDevice()),
    )
    service.bind(event_bus=bus, loop=asyncio.get_running_loop())
    await service.retry_validation()
    yield service, engine, bus, played
    await service.shutdown()


@pytest.mark.asyncio
async def test_welcome_sequence_order_and_exact_text(tts_bundle) -> None:
    service, engine, bus, played = tts_bundle
    started: list[str] = []

    async def on_utt(payload: dict) -> None:
        started.append(payload["text"])

    await bus.subscribe(TTS_UTTERANCE_STARTED, on_utt)
    finished = asyncio.Event()

    async def on_finished(_payload: dict) -> None:
        finished.set()

    await bus.subscribe(TTS_SEQUENCE_FINISHED, on_finished)

    assert service.get_status().status == TtsServiceStatus.READY
    await service.speak_welcome_sequence()
    await asyncio.wait_for(finished.wait(), timeout=5.0)

    assert engine.texts == WELCOME
    assert started == WELCOME
    assert len(played) == 3
    assert len(WELCOME) == 3
    status = service.get_status()
    assert status.status == TtsServiceStatus.READY
    assert status.last_spoken_at is not None


@pytest.mark.asyncio
async def test_duplicate_sequence_rejected(tts_settings: Settings, tmp_path: Path) -> None:
    bus = EventBus()
    engine = FakeEngine(tmp_path)
    hold = threading.Event()
    entered = threading.Event()

    def play_fn(samples, sample_rate, device_id, cancel_event) -> None:
        entered.set()
        hold.wait(timeout=5.0)

    service = TtsService(
        settings=tts_settings,
        event_bus=bus,
        engine=engine,  # type: ignore[arg-type]
        player=AudioPlayer(play_fn=play_fn),
        device_manager=AudioOutputDeviceManager(sounddevice_module=FakeSoundDevice()),
    )
    service.bind(event_bus=bus, loop=asyncio.get_running_loop())
    await service.retry_validation()

    first = asyncio.create_task(service.speak_welcome_sequence())
    await asyncio.to_thread(entered.wait, 5.0)
    with pytest.raises(SequenceBusyError):
        await service.speak_welcome_sequence()
    hold.set()
    await first
    await service.shutdown()


@pytest.mark.asyncio
async def test_cancel_clears_queue(tts_settings: Settings, tmp_path: Path) -> None:
    bus = EventBus()
    engine = FakeEngine(tmp_path)
    hold = threading.Event()
    entered = threading.Event()

    def play_fn(samples, sample_rate, device_id, cancel_event) -> None:
        entered.set()
        # Sequence cancel may reset the player cancel flag before this thread
        # observes it — also watch the test-side hold event / deadline.
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if cancel_event.is_set() or hold.is_set():
                return
            time.sleep(0.02)

    service = TtsService(
        settings=tts_settings,
        event_bus=bus,
        engine=engine,  # type: ignore[arg-type]
        player=AudioPlayer(play_fn=play_fn),
        device_manager=AudioOutputDeviceManager(sounddevice_module=FakeSoundDevice()),
    )
    service.bind(event_bus=bus, loop=asyncio.get_running_loop())
    await service.retry_validation()

    task = asyncio.create_task(service.speak_welcome_sequence())
    await asyncio.to_thread(entered.wait, 5.0)
    assert service.is_sequence_active()
    await service.cancel()
    hold.set()
    try:
        await asyncio.wait_for(task, timeout=3.0)
    except (asyncio.CancelledError, Exception):
        pass
    assert service.is_sequence_active() is False
    assert service._queue.active_sequence is None
    assert service.get_status().status == TtsServiceStatus.READY
    await service.shutdown()


@pytest.mark.asyncio
async def test_disabled_tts_status(tmp_path: Path) -> None:
    settings = Settings(
        tts_enabled=False,
        environment="development",
        tts_temp_directory=str(tmp_path / "t"),
    )
    service = TtsService(
        settings=settings,
        engine=FakeEngine(tmp_path),  # type: ignore[arg-type]
        player=AudioPlayer(play_fn=lambda *a: None),
        device_manager=AudioOutputDeviceManager(sounddevice_module=FakeSoundDevice()),
    )
    await service.on_startup()
    assert service.get_status().status == TtsServiceStatus.DISABLED
    await service.shutdown()
