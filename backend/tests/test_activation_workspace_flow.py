"""ActivationCoordinator + WorkspaceService integration — mic pause/resume across launch."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.core.config import Settings
from app.core.events import (
    ASSISTANT_WORKSPACE_INITIALIZATION_STARTED,
    ASSISTANT_WORKSPACE_READY,
    WORKSPACE_ERROR,
    EventBus,
)
from app.core.state_manager import StateManager
from app.models.application import WorkspaceProgress, WorkspaceServiceStatus, WorkspaceStatusResponse
from app.models.assistant_state import AssistantState
from app.models.tts import TtsServiceStatus
from app.services.assistant.activation_coordinator import ActivationCoordinator
from app.services.workspace.workspace_service import WorkspaceRunConflictError


class FakeVoiceService:
    def __init__(self) -> None:
        self.handoff = False
        self.paused = False
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


class FakeTtsService:
    def __init__(self) -> None:
        self.suppressed: list[bool] = []
        self.speak_calls = 0
        self.fail: Exception | None = None
        self._status = TtsServiceStatus.READY

    def set_microphone_suppressed(self, value: bool) -> None:
        self.suppressed.append(value)

    async def speak_welcome_sequence(self) -> None:
        self.speak_calls += 1
        if self.fail is not None:
            raise self.fail

    async def cancel(self) -> Any:
        return None

    def get_status(self) -> Any:
        return type("S", (), {"status": self._status})()


class FakeWorkspaceService:
    def __init__(self) -> None:
        self.start_calls = 0
        self.cancel_calls = 0
        self.result_status = WorkspaceServiceStatus.READY
        self.raise_error: Exception | None = None
        self.hold = asyncio.Event()
        self.should_hold = False
        self.entered = asyncio.Event()

    async def start_default_workspace(self) -> WorkspaceStatusResponse:
        self.start_calls += 1
        self.entered.set()
        if self.should_hold:
            await self.hold.wait()
        if self.raise_error is not None:
            raise self.raise_error
        return WorkspaceStatusResponse(
            enabled=True,
            status=self.result_status,
            profile="default",
            total_configured=3,
            total_enabled=3,
            progress=WorkspaceProgress(completed=3, total=3),
            last_error=None if self.result_status != WorkspaceServiceStatus.ERROR else "All applications failed",
        )

    async def cancel(self) -> WorkspaceStatusResponse:
        self.cancel_calls += 1
        self.hold.set()
        return WorkspaceStatusResponse(
            enabled=True,
            status=WorkspaceServiceStatus.CANCELLED,
            profile="default",
        )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        tts_enabled=True,
        tts_start_automatically=False,
        tts_pre_speech_delay_ms=0,
        tts_post_speech_delay_ms=0,
        welcome_sentence_pause_ms=0,
        workspace_enabled=True,
        workspace_start_after_welcome=True,
        workspace_ready_display_ms=0,
        environment="development",
    )


def make_coordinator(settings: Settings, workspace=None):
    bus = EventBus()
    state = StateManager(bus)
    voice = FakeVoiceService()
    tts = FakeTtsService()
    coordinator = ActivationCoordinator(settings=settings)
    coordinator.bind(
        state_manager=state,
        event_bus=bus,
        voice_service=voice,  # type: ignore[arg-type]
        tts_service=tts,  # type: ignore[arg-type]
        workspace_service=workspace,
    )
    return coordinator, state, voice, tts, bus


@pytest.mark.asyncio
async def test_workspace_launched_after_welcome_and_ready(settings: Settings) -> None:
    workspace = FakeWorkspaceService()
    coordinator, state, voice, tts, bus = make_coordinator(settings, workspace)

    events: list[str] = []

    async def on_started(_payload):
        events.append("workspace_started")

    async def on_ready(_payload):
        events.append("workspace_ready")

    await bus.subscribe(ASSISTANT_WORKSPACE_INITIALIZATION_STARTED, on_started)
    await bus.subscribe(ASSISTANT_WORKSPACE_READY, on_ready)

    await coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0)

    assert workspace.start_calls == 1
    assert events == ["workspace_started", "workspace_ready"]
    assert voice.resume_calls == 1
    assert state.current_state == AssistantState.LISTENING


@pytest.mark.asyncio
async def test_mic_stays_paused_during_workspace_launch(settings: Settings) -> None:
    workspace = FakeWorkspaceService()
    workspace.should_hold = True
    coordinator, state, voice, tts, bus = make_coordinator(settings, workspace)

    task = asyncio.create_task(coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0))
    await asyncio.wait_for(workspace.entered.wait(), timeout=3.0)

    # Speech finished, workspace launch is in progress — mic must remain paused.
    assert voice.paused is True
    assert voice.resume_calls == 0

    workspace.hold.set()
    await task
    assert voice.resume_calls == 1


@pytest.mark.asyncio
async def test_partial_success_still_resumes_and_publishes_ready(settings: Settings) -> None:
    workspace = FakeWorkspaceService()
    workspace.result_status = WorkspaceServiceStatus.PARTIAL_SUCCESS
    coordinator, state, voice, tts, bus = make_coordinator(settings, workspace)

    ready_events: list[dict] = []

    async def on_ready(payload):
        ready_events.append(payload)

    await bus.subscribe(ASSISTANT_WORKSPACE_READY, on_ready)
    await coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0)

    assert len(ready_events) == 1
    assert ready_events[0]["status"] == "PARTIAL_SUCCESS"
    assert voice.resume_calls == 1
    assert state.current_state == AssistantState.LISTENING


@pytest.mark.asyncio
async def test_workspace_error_publishes_error_but_still_resumes_mic(settings: Settings) -> None:
    workspace = FakeWorkspaceService()
    workspace.result_status = WorkspaceServiceStatus.ERROR
    coordinator, state, voice, tts, bus = make_coordinator(settings, workspace)

    error_events: list[dict] = []

    async def on_error(payload):
        error_events.append(payload)

    await bus.subscribe(WORKSPACE_ERROR, on_error)
    await coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0)

    assert len(error_events) == 1
    assert voice.resume_calls == 1
    assert state.current_state == AssistantState.LISTENING


@pytest.mark.asyncio
async def test_workspace_conflict_error_does_not_crash_activation(settings: Settings) -> None:
    workspace = FakeWorkspaceService()
    workspace.raise_error = WorkspaceRunConflictError("already running")
    coordinator, state, voice, tts, bus = make_coordinator(settings, workspace)

    error_events: list[dict] = []

    async def on_error(payload):
        error_events.append(payload)

    await bus.subscribe(WORKSPACE_ERROR, on_error)
    await coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0)

    assert len(error_events) == 1
    assert voice.resume_calls == 1


@pytest.mark.asyncio
async def test_workspace_not_launched_when_service_is_none(settings: Settings) -> None:
    coordinator, state, voice, tts, bus = make_coordinator(settings, workspace=None)
    await coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0)
    assert voice.resume_calls == 1
    assert state.current_state == AssistantState.LISTENING


@pytest.mark.asyncio
async def test_workspace_not_launched_when_start_after_welcome_false(settings: Settings) -> None:
    settings.workspace_start_after_welcome = False
    workspace = FakeWorkspaceService()
    coordinator, state, voice, tts, bus = make_coordinator(settings, workspace)
    await coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0)
    assert workspace.start_calls == 0
    assert voice.resume_calls == 1


@pytest.mark.asyncio
async def test_workspace_not_launched_when_disabled(settings: Settings) -> None:
    settings.workspace_enabled = False
    workspace = FakeWorkspaceService()
    coordinator, state, voice, tts, bus = make_coordinator(settings, workspace)
    await coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0)
    assert workspace.start_calls == 0


@pytest.mark.asyncio
async def test_tts_failure_skips_workspace_and_resumes_mic(settings: Settings) -> None:
    workspace = FakeWorkspaceService()
    coordinator, state, voice, tts, bus = make_coordinator(settings, workspace)
    tts.fail = RuntimeError("synthesis failed")

    await coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0)

    assert workspace.start_calls == 0
    assert voice.resume_calls == 1
    assert state.current_state == AssistantState.LISTENING


@pytest.mark.asyncio
async def test_cancel_also_cancels_workspace(settings: Settings) -> None:
    workspace = FakeWorkspaceService()
    workspace.should_hold = True
    coordinator, state, voice, tts, bus = make_coordinator(settings, workspace)

    task = asyncio.create_task(coordinator.handle_wake(phrase="wake up jarvis", confidence=1.0))
    await asyncio.wait_for(workspace.entered.wait(), timeout=3.0)

    await coordinator.cancel()
    try:
        await asyncio.wait_for(task, timeout=3.0)
    except asyncio.CancelledError:
        pass

    assert workspace.cancel_calls >= 1
