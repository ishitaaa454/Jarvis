"""HTTP / WebSocket API tests for the Phase 2 voice service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.models.voice import AudioDeviceInfo, VoiceServiceStatus, VoiceStatusResponse
from app.services.voice.audio_devices import AudioDeviceError
from app.services.voice.voice_service import VoiceService


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    model = tmp_path / "model"
    (model / "am").mkdir(parents=True)
    (model / "conf").mkdir()
    (model / "graph").mkdir()

    monkeypatch.setenv("VOICE_ENABLED", "true")
    monkeypatch.setenv("VOICE_START_AUTOMATICALLY", "false")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("VOSK_MODEL_PATH", str(model))
    get_settings.cache_clear()

    application = create_app()

    # Replace voice service methods that need hardware with safe stubs
    voice: VoiceService = application.state.voice_service
    voice._model_loaded = True
    voice._status = VoiceServiceStatus.STOPPED
    voice._selected_device = AudioDeviceInfo(
        id=0,
        name="Test Mic",
        host_api="Windows WASAPI",
        max_input_channels=1,
        default_sample_rate=16000,
        is_default=True,
    )

    async def fake_start() -> VoiceStatusResponse:
        voice._status = VoiceServiceStatus.LISTENING
        await voice._publish_status()
        if voice._state_manager:
            from app.models.assistant_state import AssistantState

            await voice._state_manager.set_state(AssistantState.LISTENING)
        return voice.get_status()

    async def fake_stop() -> VoiceStatusResponse:
        voice._status = VoiceServiceStatus.STOPPED
        await voice._publish_status()
        if voice._state_manager:
            from app.models.assistant_state import AssistantState

            await voice._state_manager.set_state(AssistantState.IDLE)
        return voice.get_status()

    async def fake_set_device(device_id: int) -> VoiceStatusResponse:
        if device_id != 0:
            raise AudioDeviceError("Invalid device", code="DEVICE_NOT_FOUND")
        return voice.get_status()

    def fake_list() -> list[AudioDeviceInfo]:
        assert voice._selected_device is not None
        return [voice._selected_device]

    voice.start = fake_start  # type: ignore[method-assign]
    voice.stop = fake_stop  # type: ignore[method-assign]
    voice.set_device = fake_set_device  # type: ignore[method-assign]
    voice.list_devices = fake_list  # type: ignore[method-assign]

    # Avoid real model / mic / Piper work during lifespan on_startup
    voice.on_startup = AsyncMock(return_value=None)  # type: ignore[method-assign]
    voice.shutdown = AsyncMock(return_value=None)  # type: ignore[method-assign]

    tts = application.state.tts_service
    tts.on_startup = AsyncMock(return_value=None)  # type: ignore[method-assign]
    tts.shutdown = AsyncMock(return_value=None)  # type: ignore[method-assign]
    application.state.activation_coordinator.start = AsyncMock(return_value=None)
    application.state.activation_coordinator.stop = AsyncMock(return_value=None)

    with TestClient(application) as test_client:
        yield test_client

    get_settings.cache_clear()


def test_get_voice_status(client: TestClient) -> None:
    response = client.get("/api/voice/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["status"] == "STOPPED"
    assert payload["wake_phrase"]
    assert "model_path" in payload
    # No absolute user-home leakage required — path may be tmp in tests
    assert "audio" not in payload


def test_get_voice_devices(client: TestClient) -> None:
    response = client.get("/api/voice/devices")
    assert response.status_code == 200
    devices = response.json()["devices"]
    assert len(devices) == 1
    assert devices[0]["name"] == "Test Mic"


def test_invalid_device_rejected(client: TestClient) -> None:
    response = client.put("/api/voice/device", json={"device_id": 99})
    assert response.status_code == 400


def test_start_and_stop(client: TestClient) -> None:
    started = client.post("/api/voice/start")
    assert started.status_code == 200
    assert started.json()["status"] == "LISTENING"

    stopped = client.post("/api/voice/stop")
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "STOPPED"


def test_test_activation_publishes_websocket_event(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["type"] == "connection.established"
        assert websocket.receive_json()["type"] == "state.changed"
        voice_status = websocket.receive_json()
        assert voice_status["type"] == "voice.status_changed"
        tts_status = websocket.receive_json()
        assert tts_status["type"] == "tts.status_changed"

        response = client.post("/api/voice/test-activation")
        assert response.status_code == 200

        seen_types: list[str] = []
        # Drain a few events — wake + status + state transitions
        for _ in range(8):
            message = websocket.receive_json()
            seen_types.append(message["type"])
            if message["type"] == "voice.wake_detected":
                assert "phrase" in message["payload"]
                assert "confidence" in message["payload"]
                assert "audio" not in message["payload"]
                assert "pcm" not in message["payload"]
                break
        assert "voice.wake_detected" in seen_types


def test_websocket_sends_voice_status_on_connect(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["type"] == "connection.established"
        assert websocket.receive_json()["type"] == "state.changed"
        voice_msg = websocket.receive_json()
        assert voice_msg["type"] == "voice.status_changed"
        assert "status" in voice_msg["payload"]
        tts_msg = websocket.receive_json()
        assert tts_msg["type"] == "tts.status_changed"
        assert "status" in tts_msg["payload"]


def test_missing_model_app_still_starts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VOICE_ENABLED", "true")
    monkeypatch.setenv("VOICE_START_AUTOMATICALLY", "true")
    monkeypatch.setenv("VOSK_MODEL_PATH", str(tmp_path / "no-model"))
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()

    application = create_app()
    application.state.voice_service.on_startup = AsyncMock(return_value=None)
    application.state.voice_service.shutdown = AsyncMock(return_value=None)
    application.state.tts_service.on_startup = AsyncMock(return_value=None)
    application.state.tts_service.shutdown = AsyncMock(return_value=None)
    application.state.activation_coordinator.start = AsyncMock(return_value=None)
    application.state.activation_coordinator.stop = AsyncMock(return_value=None)

    with TestClient(application) as test_client:
        health = test_client.get("/api/health")
        assert health.status_code == 200
        status = test_client.get("/api/voice/status")
        assert status.status_code == 200
        assert status.json()["status"] in {"MODEL_MISSING", "ERROR", "STOPPED"}

    get_settings.cache_clear()


def test_test_activation_hidden_in_production(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = tmp_path / "model"
    (model / "am").mkdir(parents=True)
    (model / "conf").mkdir()
    (model / "graph").mkdir()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("VOICE_START_AUTOMATICALLY", "false")
    monkeypatch.setenv("VOSK_MODEL_PATH", str(model))
    get_settings.cache_clear()

    application = create_app()
    voice = application.state.voice_service
    voice.on_startup = AsyncMock(return_value=None)
    voice.shutdown = AsyncMock(return_value=None)
    application.state.tts_service.on_startup = AsyncMock(return_value=None)
    application.state.tts_service.shutdown = AsyncMock(return_value=None)
    application.state.activation_coordinator.start = AsyncMock(return_value=None)
    application.state.activation_coordinator.stop = AsyncMock(return_value=None)

    with TestClient(application) as test_client:
        response = test_client.post("/api/voice/test-activation")
        assert response.status_code == 404

    get_settings.cache_clear()
