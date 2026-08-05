"""HTTP API tests for the Phase 4 workspace endpoints — service is fully faked."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.models.application import (
    ApplicationActionResult,
    ApplicationActionStatus,
    ApplicationRuntimeView,
    LaunchType,
    WorkspaceProgress,
    WorkspaceServiceStatus,
    WorkspaceStatusResponse,
)
from app.services.workspace.workspace_service import WorkspaceRunConflictError


class FakeWorkspaceService:
    def __init__(self) -> None:
        self.status = WorkspaceServiceStatus.IDLE
        self.started = 0
        self.cancelled = 0
        self.refreshed = 0
        self.raise_conflict = False
        self.opened: list[str] = []
        self.focused: list[str] = []
        self.unknown_ids: set[str] = set()

    def get_status(self) -> WorkspaceStatusResponse:
        return WorkspaceStatusResponse(
            enabled=True,
            status=self.status,
            active_run_id=None,
            profile="default",
            total_configured=3,
            total_enabled=3,
            current_application=None,
            progress=WorkspaceProgress(completed=0, total=3),
            last_run=None,
            last_error=None,
        )

    def list_applications(self) -> list[ApplicationRuntimeView]:
        return [
            ApplicationRuntimeView(
                id="vscode",
                display_name="Visual Studio Code",
                enabled=True,
                order=10,
                launch_type=LaunchType.EXECUTABLE,
                resolved=True,
                running=False,
                window_found=False,
                status=ApplicationActionStatus.PENDING,
            )
        ]

    async def start_default_workspace(self) -> WorkspaceStatusResponse:
        if self.raise_conflict:
            raise WorkspaceRunConflictError("A workspace run is already active")
        self.started += 1
        self.status = WorkspaceServiceStatus.READY
        return self.get_status()

    async def cancel(self) -> WorkspaceStatusResponse:
        self.cancelled += 1
        self.status = WorkspaceServiceStatus.CANCELLED
        return self.get_status()

    async def open_application(self, app_id: str) -> ApplicationActionResult:
        if app_id in self.unknown_ids or app_id == "missing":
            raise KeyError(app_id)
        self.opened.append(app_id)
        return ApplicationActionResult(
            application_id=app_id,
            display_name=app_id,
            requested_action="open",
            result="LAUNCHED",
            status=ApplicationActionStatus.READY,
        )

    async def focus_application(self, app_id: str) -> ApplicationActionResult:
        if app_id in self.unknown_ids or app_id == "missing":
            raise KeyError(app_id)
        self.focused.append(app_id)
        return ApplicationActionResult(
            application_id=app_id,
            display_name=app_id,
            requested_action="focus",
            result="FOCUSED",
            status=ApplicationActionStatus.READY,
        )

    def refresh(self) -> WorkspaceStatusResponse:
        self.refreshed += 1
        return self.get_status()

    def bind(self, *, event_bus) -> None:
        return None

    async def on_startup(self) -> None:
        return None


@pytest.fixture
def fake_service() -> FakeWorkspaceService:
    return FakeWorkspaceService()


@pytest.fixture
def client(fake_service: FakeWorkspaceService) -> TestClient:
    get_settings.cache_clear()
    application = create_app()
    application.state.voice_service.on_startup = AsyncMock(return_value=None)
    application.state.voice_service.shutdown = AsyncMock(return_value=None)
    application.state.tts_service.on_startup = AsyncMock(return_value=None)
    application.state.tts_service.shutdown = AsyncMock(return_value=None)
    application.state.activation_coordinator.start = AsyncMock(return_value=None)
    application.state.activation_coordinator.stop = AsyncMock(return_value=None)
    application.state.workspace_service = fake_service
    with TestClient(application) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_get_workspace_status(client: TestClient) -> None:
    response = client.get("/api/workspace/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "IDLE"
    assert payload["total_enabled"] == 3


def test_list_workspace_applications(client: TestClient) -> None:
    response = client.get("/api/workspace/applications")
    assert response.status_code == 200
    apps = response.json()["applications"]
    assert len(apps) == 1
    assert apps[0]["id"] == "vscode"


def test_start_workspace_in_development(client: TestClient, fake_service: FakeWorkspaceService) -> None:
    response = client.post("/api/workspace/start")
    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert fake_service.started == 1


def test_start_workspace_conflict_returns_409(
    client: TestClient, fake_service: FakeWorkspaceService
) -> None:
    fake_service.raise_conflict = True
    response = client.post("/api/workspace/start")
    assert response.status_code == 409


def test_start_workspace_hidden_in_production(fake_service: FakeWorkspaceService) -> None:
    import os

    os.environ["ENVIRONMENT"] = "production"
    os.environ["WORKSPACE_MANUAL_START_IN_PRODUCTION"] = "false"
    get_settings.cache_clear()
    try:
        application = create_app()
        application.state.voice_service.on_startup = AsyncMock(return_value=None)
        application.state.voice_service.shutdown = AsyncMock(return_value=None)
        application.state.tts_service.on_startup = AsyncMock(return_value=None)
        application.state.tts_service.shutdown = AsyncMock(return_value=None)
        application.state.activation_coordinator.start = AsyncMock(return_value=None)
        application.state.activation_coordinator.stop = AsyncMock(return_value=None)
        application.state.workspace_service = fake_service
        with TestClient(application) as test_client:
            response = test_client.post("/api/workspace/start")
            assert response.status_code == 404
    finally:
        os.environ["ENVIRONMENT"] = "development"
        get_settings.cache_clear()


def test_start_workspace_allowed_in_production_when_flag_set(
    fake_service: FakeWorkspaceService,
) -> None:
    import os

    os.environ["ENVIRONMENT"] = "production"
    os.environ["WORKSPACE_MANUAL_START_IN_PRODUCTION"] = "true"
    get_settings.cache_clear()
    try:
        application = create_app()
        application.state.voice_service.on_startup = AsyncMock(return_value=None)
        application.state.voice_service.shutdown = AsyncMock(return_value=None)
        application.state.tts_service.on_startup = AsyncMock(return_value=None)
        application.state.tts_service.shutdown = AsyncMock(return_value=None)
        application.state.activation_coordinator.start = AsyncMock(return_value=None)
        application.state.activation_coordinator.stop = AsyncMock(return_value=None)
        application.state.workspace_service = fake_service
        with TestClient(application) as test_client:
            response = test_client.post("/api/workspace/start")
            assert response.status_code == 200
    finally:
        os.environ["ENVIRONMENT"] = "development"
        os.environ["WORKSPACE_MANUAL_START_IN_PRODUCTION"] = "false"
        get_settings.cache_clear()


def test_cancel_workspace(client: TestClient, fake_service: FakeWorkspaceService) -> None:
    response = client.post("/api/workspace/cancel")
    assert response.status_code == 200
    assert fake_service.cancelled == 1


def test_open_application(client: TestClient, fake_service: FakeWorkspaceService) -> None:
    response = client.post("/api/workspace/applications/vscode/open")
    assert response.status_code == 200
    assert fake_service.opened == ["vscode"]


def test_open_unknown_application_returns_404(client: TestClient) -> None:
    response = client.post("/api/workspace/applications/missing/open")
    assert response.status_code == 404


def test_focus_application(client: TestClient, fake_service: FakeWorkspaceService) -> None:
    response = client.post("/api/workspace/applications/vscode/focus")
    assert response.status_code == 200
    assert fake_service.focused == ["vscode"]


def test_focus_unknown_application_returns_404(client: TestClient) -> None:
    response = client.post("/api/workspace/applications/missing/focus")
    assert response.status_code == 404


def test_refresh_workspace(client: TestClient, fake_service: FakeWorkspaceService) -> None:
    response = client.post("/api/workspace/refresh")
    assert response.status_code == 200
    assert fake_service.refreshed == 1


def test_status_response_never_exposes_command_lines(client: TestClient) -> None:
    response = client.get("/api/workspace/status")
    text = response.text.lower()
    assert "cmd.exe" not in text
    assert "subprocess" not in text
