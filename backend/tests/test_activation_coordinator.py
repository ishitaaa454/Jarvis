"""ActivationCoordinator tests with fake VoiceService and TtsService."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.core.config import Settings
from app.core.events import (
    ASSISTANT_ACTIVATION_FINISHED,
    ASSISTANT_ACTIVATION_STARTED,
    EventBus,
)
from app.core.state_manager import StateManager
from app.models.assistant_state import AssistantState
from app.models.tts import TtsServiceStatus
from app.services.assistant.activation_coordinator import ActivationCoordinator
from app.services.tts.tts_service import SequenceBusyError


class FakeVoiceService:
    def __init__(self) -> None:
        self.handoff = False
        self.paused = False
        self.resumed = False
        self.capture_active = True
        self.pause_calls = 0
        self.resume_calls = 0

    def set_activation_handoff(self, enabled: bool) -> None:
        self.handoff = enabled

    def is_capture_active(self) -> bool:
        return self.capture_active and not self.paused

    async def pause_listening(self) -> None:
        self.pause_calls += 1
        self.paused = True

    async def resume_listening(self) -> None:
        self.resume_calls += 1
        self.paused = False
        self.resumed = True


class FakeTtsService:
    def __init__(self) -> None:
        self.suppressed: list[bool] = []
        self.speak_calls = 0
        self.cancel_calls = 0
        self.hold = asyncio.Event()
        self.entered = asyncio.Event()
        self.should_hold = False
        self.fail: Exception | None = None
        self._status = TtsServiceStatus.READY

    def set_microphone_suppressed(self, value: bool) -> None:
        self.suppressed.append(value)

    async def speak_welcome_sequence(self) -> None:
        self.speak_calls += 1
        self.entered.set()
        if self.fail is not None:
            raise self.fail
        if self.should_hold:
            await self.hold.wait()

    async def cancel(self) -> Any:
        self.cancel_calls += 1
        self.hold.set()
        return None

    def get_status(self) -> Any:
        return type("S", (), {"status": self._status})()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        tts_enabled=True,
        tts_start_automatically=False,
        tts_pre_speech_delay_ms=0,
        tts_post_speech_delay_ms=0,
        welcome_sentence_pause_ms=0,
        environment="development",
    )


@pytest.fixture
async def coordinator_bundle(settings: Settings):
    bus = EventBus()
    state = StateManager(bus)
    voice = FakeVoiceService()
    tts = FakeTtsService()
    coordinator = ActivationCoordinator(
        settings=settings,
        state_manager=state,
        event_bus=bus,
        voice_service=voice,  # type: ignore[arg-type]
        tts_service=tts,  # type: ignore[arg-type]
    )
    coordinator.bind(
        state_manager=state,
        event_bus=bus,
        voice_service=voice,  # type: ignore[arg-type]
        tts_service=tts,  # type: ignore[arg-type]
    )
    await coordinator.start()
    yield coordinator, state, voice, tts, bus
    await coordinator.stop()


@pytest.mark.asyncio
async def test_bind_sets_activation_handoff(coordinator_bundle) -> None:
    _coordinator, _state, voice, _tts, _bus = coordinator_bundle
    assert voice.handoff is True


@pytest.mark.asyncio
async def test_pauses_then_resumes_voice(coordinator_bundle) -> None:
    coordinator, state, voice, tts, bus = coordinator_bundle
    started = asyncio.Event()
    finished = asyncio.Event()

    async def on_started(_payload: dict) -> None:
        started.set()

    async def on_finished(_payload: dict) -> None:
        finished.set()

    await bus.subscribe(ASSISTANT_ACTIVATION_STARTED, on_started)
    await bus.subscribe(ASSISTANT_ACTIVATION_FINISHED, on_finished)

    await coordinator.handle_wake(phrase="wake up jarvis", confidence=0.9)
    await asyncio.wait_for(finished.wait(), timeout=3.0)

    assert voice.pause_calls == 1
    assert voice.resume_calls == 1
    assert tts.speak_calls == 1
    assert tts.suppressed == [True, False]
    assert state.current_state == AssistantState.LISTENING
    assert started.is_set()


@pytest.mark.asyncio
async def test_state_processing_speaking_listening(settings: Settings) -> None:
    bus = EventBus()
    state = StateManager(bus)
    voice = FakeVoiceService()
    tts = FakeTtsService()
    tts.should_hold = True
    states: list[AssistantState] = []

    original_set = state.set_state

    async def tracking_set(new_state: AssistantState | str):
        states.append(new_state if isinstance(new_state, AssistantState) else AssistantState(new_state))
        return await original_set(new_state)

    state.set_state = tracking_set  # type: ignore[method-assign]

    coordinator = ActivationCoordinator(settings=settings)
    coordinator.bind(
        state_manager=state,
        event_bus=bus,
        voice_service=voice,  # type: ignore[arg-type]
        tts_service=tts,  # type: ignore[arg-type]
    )

    task = asyncio.create_task(
        coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0)
    )
    await asyncio.wait_for(tts.entered.wait(), timeout=3.0)
    # During speech hold: PROCESSING then SPEAKING should already be set
    assert AssistantState.PROCESSING in states
    assert AssistantState.SPEAKING in states
    assert state.current_state == AssistantState.SPEAKING

    tts.hold.set()
    await task
    assert state.current_state == AssistantState.LISTENING
    assert states[-1] == AssistantState.LISTENING


@pytest.mark.asyncio
async def test_duplicate_activation_rejected(settings: Settings) -> None:
    bus = EventBus()
    state = StateManager(bus)
    voice = FakeVoiceService()
    tts = FakeTtsService()
    tts.should_hold = True

    coordinator = ActivationCoordinator(settings=settings)
    coordinator.bind(
        state_manager=state,
        event_bus=bus,
        voice_service=voice,  # type: ignore[arg-type]
        tts_service=tts,  # type: ignore[arg-type]
    )

    first = asyncio.create_task(coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0))
    await asyncio.wait_for(tts.entered.wait(), timeout=3.0)
    with pytest.raises(SequenceBusyError):
        await coordinator.handle_wake(phrase="wake up jarvis", confidence=0.8)
    tts.hold.set()
    await first


@pytest.mark.asyncio
async def test_cancel_resumes_listening(coordinator_bundle) -> None:
    coordinator, state, voice, tts, _bus = coordinator_bundle
    tts.should_hold = True
    task = asyncio.create_task(coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0))
    await asyncio.wait_for(tts.entered.wait(), timeout=3.0)
    await coordinator.cancel()
    try:
        await asyncio.wait_for(task, timeout=3.0)
    except asyncio.CancelledError:
        pass
    assert voice.resume_calls >= 1
    assert state.current_state == AssistantState.LISTENING
    assert coordinator.is_active is False
