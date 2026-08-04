"""HTTP and WebSocket API tests for Phase 1."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.assistant_state import AssistantState


@pytest.fixture
def client() -> TestClient:
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_contains_required_fields(client: TestClient) -> None:
    payload = client.get("/api/health").json()
    assert payload["status"] == "online"
    assert payload["service"] == "jarvis-backend"
    assert "version" in payload
    assert "timestamp" in payload
    assert "system" in payload
    assert "platform" in payload["system"]
    assert "cpu_percent" in payload["system"]
    assert "memory_percent" in payload["system"]
    assert isinstance(payload["system"]["cpu_percent"], (int, float))
    assert isinstance(payload["system"]["memory_percent"], (int, float))


def test_initial_state_is_idle(client: TestClient) -> None:
    payload = client.get("/api/state").json()
    assert payload["state"] == AssistantState.IDLE.value


def test_valid_state_transition(client: TestClient) -> None:
    response = client.post("/api/state/LISTENING")
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "LISTENING"
    assert payload["previous_state"] == "IDLE"


def test_invalid_state_rejected(client: TestClient) -> None:
    response = client.post("/api/state/NOT_A_REAL_STATE")
    assert response.status_code == 400
    body = response.json()
    assert body.get("error") is True or "detail" in body


def test_websocket_receives_connection_event(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "connection.established"
        assert "timestamp" in message
        assert message["payload"]["message"] == "Connected to Jarvis backend"

        state_message = websocket.receive_json()
        assert state_message["type"] == "state.changed"
        assert "state" in state_message["payload"]

        voice_message = websocket.receive_json()
        assert voice_message["type"] == "voice.status_changed"
        assert "status" in voice_message["payload"]
