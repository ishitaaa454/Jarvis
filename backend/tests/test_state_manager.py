"""Unit tests for StateManager behavior."""

from __future__ import annotations

import pytest

from app.core.events import STATE_CHANGED, EventBus
from app.core.state_manager import InvalidStateError, StateManager
from app.models.assistant_state import AssistantState


@pytest.mark.asyncio
async def test_state_manager_stores_previous_state() -> None:
    bus = EventBus()
    manager = StateManager(bus)

    await manager.set_state(AssistantState.STARTING)
    snapshot = await manager.set_state(AssistantState.IDLE)

    assert snapshot.state == AssistantState.IDLE
    assert snapshot.previous_state == AssistantState.STARTING


@pytest.mark.asyncio
async def test_state_manager_publishes_state_change_event() -> None:
    bus = EventBus()
    manager = StateManager(bus)
    received: list[dict] = []

    async def handler(payload: dict) -> None:
        received.append(payload)

    await bus.subscribe(STATE_CHANGED, handler)
    await manager.set_state(AssistantState.STARTING)
    await manager.set_state(AssistantState.IDLE)

    assert len(received) == 2
    assert received[-1]["state"] == "IDLE"
    assert received[-1]["previous_state"] == "STARTING"


@pytest.mark.asyncio
async def test_state_manager_rejects_invalid_state() -> None:
    bus = EventBus()
    manager = StateManager(bus)

    with pytest.raises(InvalidStateError):
        await manager.set_state("TOTALLY_INVALID")
