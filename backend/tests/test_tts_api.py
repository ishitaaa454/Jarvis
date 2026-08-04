"""HTTP / WebSocket API tests for the Phase 3 TTS service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.models.tts import OutputDeviceInfo, TtsServiceStatus, TtsStatusResponse
from app.services.tts.audio_output_devices import AudioOutputError
from app.services.tts.tts_service import TtsService


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    model = tmp_path / "model"
    (model / "am").mkdir(parents=True)
    (model / "conf").mkdir()
    (model / "graph").mkdir()

    monkeypatch.setenv("VOICE_ENABLED", "true")
    monkeypatch.setenv("VOICE_START_AUTOMATICALLY", "false")
    monkeypatch.setenv("TTS_ENABLED", "true")
    monkeypatch.setenv("TTS_START_AUTOMATICALLY", "false")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("VOSK_MODEL_PATH", str(model))
    get_settings.cache_clear()

    application = create_app()

    voice = application.state.voice_service
    voice.on_startup = AsyncMock(return_value=None)
    voice.shutdown = AsyncMock(return_value=None)

    tts: TtsService = application.state.tts_service
    tts._model_loaded = True
    tts._status = TtsServiceStatus.READY
    tts._selected_device = OutputDeviceInfo(
        id=0,
        name="Test Speakers",
        host_api="Windows WASAPI",
        max_output_channels=2,
        default_sample_rate=48000,
        is_default=True,
    )

    device = tts._selected_device

    def fake_list() -> list[OutputDeviceInfo]:
        return [device]

    async def fake_set_device(device_id: int) -> TtsStatusResponse:
        if device_id != 0:
            raise AudioOutputError("Invalid device", code="OUTPUT_NOT_FOUND")
        return tts.get_status()

    async def fake_cancel() -> TtsStatusResponse:
        return tts.get_status()

    tts.list_devices = fake_list  # type: ignore[method-assign]
    tts.set_device = fake_set_device  # type: ignore[method-assign]
    tts.on_startup = AsyncMock(return_value=None)  # type: ignore[method-assign]
    tts.shutdown = AsyncMock(return_value=None)  # type: ignore[method-assign]
    tts.cancel = fake_cancel  # type: ignore[method-assign]
    tts.retry_validation = AsyncMock(return_value=tts.get_status())  # type: ignore[method-assign]

    coordinator = application.state.activation_coordinator
    coordinator.run_test_welcome = AsyncMock(return_value=None)
    coordinator.cancel = AsyncMock(return_value=None)
    coordinator.start = AsyncMock(return_value=None)
    coordinator.stop = AsyncMock(return_value=None)

    with TestClient(application) as test_client:
        yield test_client

    get_settings.cache_clear()


def test_get_tts_status(client: TestClient) -> None:
    response = client.get("/api/tts/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["status"] == "READY"
    assert payload["engine"] == "Piper"
    assert payload["voice"] == "en_GB-alan-medium"
    assert "model_loaded" in payload


def test_get_tts_devices(client: TestClient) -> None:
    response = client.get("/api/tts/devices")
    assert response.status_code == 200
    devices = response.json()["devices"]
    assert len(devices) == 1
    assert devices[0]["name"] == "Test Speakers"


def test_invalid_device_rejected(client: TestClient) -> None:
    response = client.put("/api/tts/device", json={"device_id": 99})
    assert response.status_code == 400


def test_cancel_idempotent(client: TestClient) -> None:
    first = client.post("/api/tts/cancel")
    assert first.status_code == 200
    second = client.post("/api/tts/cancel")
    assert second.status_code == 200
    assert second.json()["status"] == "READY"


def test_test_welcome_available_in_development(client: TestClient) -> None:
    response = client.post("/api/tts/test-welcome")
    assert response.status_code == 200


def test_test_welcome_hidden_in_production(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = tmp_path / "model"
    (model / "am").mkdir(parents=True)
    (model / "conf").mkdir()
    (model / "graph").mkdir()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("VOICE_START_AUTOMATICALLY", "false")
    monkeypatch.setenv("TTS_START_AUTOMATICALLY", "false")
    monkeypatch.setenv("VOSK_MODEL_PATH", str(model))
    get_settings.cache_clear()

    application = create_app()
    application.state.voice_service.on_startup = AsyncMock(return_value=None)
    application.state.voice_service.shutdown = AsyncMock(return_value=None)
    application.state.tts_service.on_startup = AsyncMock(return_value=None)
    application.state.tts_service.shutdown = AsyncMock(return_value=None)
    application.state.activation_coordinator.start = AsyncMock(return_value=None)
    application.state.activation_coordinator.stop = AsyncMock(return_value=None)

    with TestClient(application) as test_client:
        response = test_client.post("/api/tts/test-welcome")
        assert response.status_code == 404

    get_settings.cache_clear()


def test_missing_piper_app_still_starts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = tmp_path / "model"
    (model / "am").mkdir(parents=True)
    (model / "conf").mkdir()
    (model / "graph").mkdir()
    monkeypatch.setenv("VOICE_ENABLED", "true")
    monkeypatch.setenv("VOICE_START_AUTOMATICALLY", "false")
    monkeypatch.setenv("TTS_ENABLED", "true")
    monkeypatch.setenv("TTS_START_AUTOMATICALLY", "true")
    monkeypatch.setenv("PIPER_EXECUTABLE_PATH", str(tmp_path / "no-piper.exe"))
    monkeypatch.setenv(
        "PIPER_VOICE_MODEL_PATH", str(tmp_path / "missing" / "voice.onnx")
    )
    monkeypatch.setenv(
        "PIPER_VOICE_CONFIG_PATH", str(tmp_path / "missing" / "voice.onnx.json")
    )
    monkeypatch.setenv("VOSK_MODEL_PATH", str(model))
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()

    application = create_app()
    application.state.voice_service.on_startup = AsyncMock(return_value=None)
    application.state.voice_service.shutdown = AsyncMock(return_value=None)

    with TestClient(application) as test_client:
        health = test_client.get("/api/health")
        assert health.status_code == 200
        status = test_client.get("/api/tts/status")
        assert status.status_code == 200
        assert status.json()["status"] in {
            "ENGINE_MISSING",
            "MODEL_MISSING",
            "ERROR",
            "STOPPED",
            "OUTPUT_UNAVAILABLE",
            "READY",
            "VALIDATING",
        }

    get_settings.cache_clear()


def test_websocket_sends_tts_status_on_connect(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["type"] == "connection.established"
        assert websocket.receive_json()["type"] == "state.changed"
        voice_msg = websocket.receive_json()
        assert voice_msg["type"] == "voice.status_changed"
        tts_msg = websocket.receive_json()
        assert tts_msg["type"] == "tts.status_changed"
        assert "status" in tts_msg["payload"]
