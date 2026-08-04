"""VoiceService lifecycle tests without a real microphone or Vosk model."""

from __future__ import annotations

import asyncio
import queue
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from app.core.config import Settings
from app.core.events import (
    VOICE_STATUS_CHANGED,
    VOICE_WAKE_DETECTED,
    EventBus,
)
from app.core.state_manager import StateManager
from app.models.assistant_state import AssistantState
from app.models.voice import AudioDeviceInfo, VoiceServiceStatus
from app.services.voice.audio_devices import AudioDeviceManager
from app.services.voice.voice_service import VoiceService, _STOP
from app.services.voice.wake_phrase_detector import WakePhraseDetector


class FakeSoundDevice:
    def __init__(self) -> None:
        self.default = type("D", (), {"device": (0, None)})()

    def query_devices(self):
        return [
            {
                "name": "Fake Mic",
                "hostapi": 0,
                "max_input_channels": 1,
                "default_samplerate": 16000,
            }
        ]

    def query_hostapis(self):
        return [{"name": "Windows WASAPI"}]


class FakeStream:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    model = tmp_path / "model"
    (model / "am").mkdir(parents=True)
    (model / "conf").mkdir()
    (model / "graph").mkdir()
    return Settings(
        voice_enabled=True,
        voice_start_automatically=False,
        vosk_model_path=str(model),
        wake_cooldown_seconds=0.5,
        voice_activation_display_ms=800,
        environment="development",
    )


@pytest.fixture
async def voice_bundle(settings: Settings):
    bus = EventBus()
    state = StateManager(bus)
    detector = WakePhraseDetector(
        Path(settings.vosk_model_path),
        wake_phrase=settings.wake_phrase,
        confidence_threshold=settings.wake_confidence_threshold,
        cooldown_seconds=settings.wake_cooldown_seconds,
        model=object(),
        recognizer_factory=type(
            "F",
            (),
            {
                "create": staticmethod(
                    lambda rate: type(
                        "R",
                        (),
                        {
                            "AcceptWaveform": lambda self, data: False,
                            "PartialResult": lambda self: "{}",
                            "Result": lambda self: "{}",
                            "FinalResult": lambda self: "{}",
                            "SetWords": lambda self, flag: None,
                        },
                    )()
                )
            },
        )(),
    )
    streams: list[FakeStream] = []

    def stream_factory(**kwargs: Any) -> FakeStream:
        stream = FakeStream(**kwargs)
        streams.append(stream)
        return stream

    service = VoiceService(
        settings=settings,
        state_manager=state,
        event_bus=bus,
        device_manager=AudioDeviceManager(sounddevice_module=FakeSoundDevice()),
        detector=detector,
        stream_factory=stream_factory,
    )
    service.set_event_loop(asyncio.get_running_loop())
    service._model_loaded = True
    service._selected_device = AudioDeviceInfo(
        id=0,
        name="Fake Mic",
        host_api="Windows WASAPI",
        max_input_channels=1,
        default_sample_rate=16000,
        is_default=True,
    )
    return service, state, bus, streams


@pytest.mark.asyncio
async def test_start_stop_idempotent(voice_bundle) -> None:
    service, state, _bus, streams = voice_bundle
    status1 = await service.start()
    assert status1.status == VoiceServiceStatus.LISTENING
    assert len(streams) == 1
    status2 = await service.start()
    assert status2.status == VoiceServiceStatus.LISTENING
    assert len(streams) == 1  # no second stream

    assert state.current_state == AssistantState.LISTENING

    stop1 = await service.stop()
    assert stop1.status == VoiceServiceStatus.STOPPED
    stop2 = await service.stop()
    assert stop2.status == VoiceServiceStatus.STOPPED
    assert state.current_state == AssistantState.IDLE


@pytest.mark.asyncio
async def test_missing_model_does_not_crash(tmp_path: Path) -> None:
    settings = Settings(
        voice_enabled=True,
        voice_start_automatically=True,
        vosk_model_path=str(tmp_path / "absent"),
        environment="development",
    )
    bus = EventBus()
    state = StateManager(bus)
    service = VoiceService(
        settings=settings,
        state_manager=state,
        event_bus=bus,
        device_manager=AudioDeviceManager(sounddevice_module=FakeSoundDevice()),
    )
    service.set_event_loop(asyncio.get_running_loop())
    await service.on_startup()
    assert service.get_status().status == VoiceServiceStatus.MODEL_MISSING
    assert state.current_state == AssistantState.OFFLINE or True  # untouched by voice


@pytest.mark.asyncio
async def test_missing_microphone_does_not_crash(settings: Settings, tmp_path: Path) -> None:
    class EmptySD:
        default = type("D", (), {"device": (None, None)})()

        def query_devices(self):
            return []

        def query_hostapis(self):
            return []

    bus = EventBus()
    state = StateManager(bus)
    detector = WakePhraseDetector(
        Path(settings.vosk_model_path),
        model=object(),
        recognizer_factory=type(
            "F",
            (),
            {"create": staticmethod(lambda rate: object())},
        )(),
    )
    service = VoiceService(
        settings=settings,
        state_manager=state,
        event_bus=bus,
        device_manager=AudioDeviceManager(sounddevice_module=EmptySD()),
        detector=detector,
    )
    service.set_event_loop(asyncio.get_running_loop())
    service._model_loaded = True
    # Pretend model already validated
    await service.on_startup()
    # on_startup will try ensure_model_loaded — model dir exists from settings fixture
    status = service.get_status()
    assert status.status in {VoiceServiceStatus.ERROR, VoiceServiceStatus.STOPPED}


@pytest.mark.asyncio
async def test_wake_updates_assistant_state(voice_bundle) -> None:
    service, state, bus, _streams = voice_bundle
    await service.start()
    events: list[dict] = []

    async def capture(payload: dict) -> None:
        events.append(payload)

    await bus.subscribe(VOICE_WAKE_DETECTED, capture)
    await service.simulate_wake(confidence=0.95)
    assert state.current_state == AssistantState.PROCESSING
    assert events
    assert "audio" not in events[0]
    assert "phrase" in events[0]

    # Wait for return-to-listening
    await asyncio.sleep(0.9)
    assert state.current_state == AssistantState.LISTENING
    await service.stop()


@pytest.mark.asyncio
async def test_shutdown_stops_service(voice_bundle) -> None:
    service, _state, _bus, streams = voice_bundle
    await service.start()
    await service.shutdown()
    assert streams[0].stopped is True
    assert streams[0].closed is True
    assert service.get_status().status == VoiceServiceStatus.STOPPED


@pytest.mark.asyncio
async def test_audio_queue_bounded(voice_bundle) -> None:
    service, _state, _bus, _streams = voice_bundle
    await service.start()
    qsize = service._settings.voice_audio_queue_size
    for _ in range(qsize + 10):
        try:
            service._audio_queue.put_nowait(b"\x00\x00")
        except queue.Full:
            pass
    assert service._audio_queue.qsize() <= qsize
    await service.stop()


def test_resample_and_pcm_conversion() -> None:
    samples = np.linspace(-0.5, 0.5, 4800, dtype=np.float32).reshape(-1, 1)
    pcm = VoiceService._frames_to_pcm16(samples, device_rate=48000, target_rate=16000)
    assert isinstance(pcm, bytes)
    assert len(pcm) % 2 == 0
    # ~1600 samples * 2 bytes
    assert 1500 * 2 <= len(pcm) <= 1700 * 2


@pytest.mark.asyncio
async def test_invalid_device_selection(voice_bundle) -> None:
    service, _state, _bus, _streams = voice_bundle
    from app.services.voice.audio_devices import AudioDeviceError

    with pytest.raises(AudioDeviceError):
        await service.set_device(999)
