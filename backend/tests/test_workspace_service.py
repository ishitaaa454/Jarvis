"""WorkspaceService orchestration tests — application controller is fully faked."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.events import (
    WORKSPACE_APPLICATION_RESULT,
    WORKSPACE_APPLICATION_STATUS,
    WORKSPACE_RUN_CANCELLED,
    WORKSPACE_RUN_FINISHED,
    WORKSPACE_RUN_STARTED,
    WORKSPACE_STATUS_CHANGED,
    EventBus,
)
from app.models.application import ApplicationActionResult, ApplicationActionStatus, WorkspaceServiceStatus
from app.services.workspace.app_registry import AppRegistry
from app.services.workspace.workspace_service import (
    WorkspaceRunConflictError,
    WorkspaceService,
)

SAMPLE_CONFIG = {
    "profile": "default",
    "applications": [
        {
            "id": "vscode",
            "display_name": "Visual Studio Code",
            "enabled": True,
            "launch_type": "executable",
            "executable_candidates": ["code.cmd"],
            "process_names": ["Code.exe"],
            "order": 10,
        },
        {
            "id": "chrome",
            "display_name": "Google Chrome",
            "enabled": True,
            "launch_type": "executable",
            "executable_candidates": ["chrome.exe"],
            "process_names": ["chrome.exe"],
            "order": 20,
        },
        {
            "id": "gmail",
            "display_name": "Gmail",
            "enabled": True,
            "launch_type": "browser_url",
            "process_names": ["chrome.exe"],
            "url": "https://mail.google.com/",
            "order": 30,
        },
    ],
}


class FakeApplicationController:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.results: dict[str, ApplicationActionResult] = {}
        self.default_status = ApplicationActionStatus.READY
        self.hold_for: str | None = None
        self.hold_event = asyncio.Event()
        self.entered_hold = asyncio.Event()

    def _default_result(self, app) -> ApplicationActionResult:
        return ApplicationActionResult(
            application_id=app.id,
            display_name=app.display_name,
            requested_action="open",
            result="LAUNCHED",
            running=True,
            status=self.default_status,
        )

    async def open_one(self, app, *, on_status=None, cancel_event=None):
        self.calls.append(app.id)
        if on_status is not None:
            await on_status(ApplicationActionStatus.CHECKING, {})
        if self.hold_for == app.id:
            self.entered_hold.set()
            await self.hold_event.wait()
        return self.results.get(app.id, self._default_result(app))

    def probe(self, app):
        return True, False, False

    async def focus_one(self, app):
        return ApplicationActionResult(
            application_id=app.id,
            display_name=app.display_name,
            requested_action="focus",
            result="FOCUSED",
            status=ApplicationActionStatus.READY,
        )


def write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "applications.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="development",
        workspace_inter_app_delay_ms=0,
        workspace_ready_display_ms=0,
    )


@pytest.fixture
def service_bundle(tmp_path: Path, settings: Settings):
    config_path = write_config(tmp_path, SAMPLE_CONFIG)
    registry = AppRegistry(settings=settings, config_path=config_path)
    controller = FakeApplicationController()
    bus = EventBus()
    service = WorkspaceService(
        settings=settings,
        event_bus=bus,
        app_registry=registry,
        application_controller=controller,
    )
    return service, controller, bus, registry


@pytest.mark.asyncio
async def test_start_default_workspace_launches_all_in_order(service_bundle) -> None:
    service, controller, _bus, _registry = service_bundle
    status = await service.start_default_workspace()

    assert controller.calls == ["vscode", "chrome", "gmail"]
    assert status.status == WorkspaceServiceStatus.READY
    assert status.last_run is not None
    assert status.last_run.successful == 3
    assert status.last_run.failed == 0


@pytest.mark.asyncio
async def test_partial_success_when_some_apps_fail(service_bundle) -> None:
    service, controller, _bus, _registry = service_bundle
    controller.results["chrome"] = ApplicationActionResult(
        application_id="chrome",
        display_name="Google Chrome",
        requested_action="open",
        result="FAILED",
        status=ApplicationActionStatus.FAILED,
        error="Executable could not be resolved",
    )

    status = await service.start_default_workspace()

    assert status.status == WorkspaceServiceStatus.PARTIAL_SUCCESS
    assert status.last_run.failed == 1
    assert status.last_run.successful == 2


@pytest.mark.asyncio
async def test_error_status_when_all_apps_fail(service_bundle) -> None:
    service, controller, _bus, _registry = service_bundle
    for app_id in ("vscode", "chrome", "gmail"):
        controller.results[app_id] = ApplicationActionResult(
            application_id=app_id,
            display_name=app_id,
            requested_action="open",
            result="FAILED",
            status=ApplicationActionStatus.FAILED,
            error="boom",
        )

    status = await service.start_default_workspace()
    assert status.status == WorkspaceServiceStatus.ERROR
    assert status.last_error is not None


@pytest.mark.asyncio
async def test_continue_on_error_true_runs_remaining_apps(service_bundle) -> None:
    service, controller, _bus, _registry = service_bundle
    controller.results["vscode"] = ApplicationActionResult(
        application_id="vscode",
        display_name="vscode",
        requested_action="open",
        result="FAILED",
        status=ApplicationActionStatus.FAILED,
        error="boom",
    )
    await service.start_default_workspace()
    assert controller.calls == ["vscode", "chrome", "gmail"]


@pytest.mark.asyncio
async def test_continue_on_error_false_stops_after_failure(tmp_path: Path) -> None:
    settings = Settings(
        environment="development",
        workspace_inter_app_delay_ms=0,
        workspace_continue_on_application_error=False,
    )
    config_path = write_config(tmp_path, SAMPLE_CONFIG)
    registry = AppRegistry(settings=settings, config_path=config_path)
    controller = FakeApplicationController()
    controller.results["vscode"] = ApplicationActionResult(
        application_id="vscode",
        display_name="vscode",
        requested_action="open",
        result="FAILED",
        status=ApplicationActionStatus.FAILED,
        error="boom",
    )
    service = WorkspaceService(
        settings=settings,
        event_bus=EventBus(),
        app_registry=registry,
        application_controller=controller,
    )

    status = await service.start_default_workspace()
    assert controller.calls == ["vscode"]
    assert status.last_run.total_applications == 3
    assert status.last_run.skipped == 2


@pytest.mark.asyncio
async def test_duplicate_run_raises_conflict(service_bundle) -> None:
    service, controller, _bus, _registry = service_bundle
    controller.hold_for = "vscode"

    task = asyncio.create_task(service.start_default_workspace())
    await asyncio.wait_for(controller.entered_hold.wait(), timeout=2.0)

    with pytest.raises(WorkspaceRunConflictError):
        await service.start_default_workspace()

    controller.hold_event.set()
    await task


@pytest.mark.asyncio
async def test_cancel_marks_remaining_apps_cancelled(service_bundle) -> None:
    service, controller, _bus, _registry = service_bundle
    controller.hold_for = "vscode"

    task = asyncio.create_task(service.start_default_workspace())
    await asyncio.wait_for(controller.entered_hold.wait(), timeout=2.0)

    # Request cancellation while "vscode" is still in-flight, then let it finish
    # so the run loop observes the cancel flag before starting the next app.
    cancel_task = asyncio.create_task(service.cancel())
    await asyncio.sleep(0.05)
    controller.hold_event.set()

    status = await asyncio.wait_for(task, timeout=3.0)
    await cancel_task

    assert status.status == WorkspaceServiceStatus.CANCELLED
    assert status.last_run.status == WorkspaceServiceStatus.CANCELLED
    assert controller.calls == ["vscode"]


@pytest.mark.asyncio
async def test_cancel_when_idle_is_noop(service_bundle) -> None:
    service, _controller, _bus, _registry = service_bundle
    status = await service.cancel()
    assert status.status == WorkspaceServiceStatus.IDLE


@pytest.mark.asyncio
async def test_events_published_in_order(service_bundle) -> None:
    service, _controller, bus, _registry = service_bundle
    seen: list[str] = []

    async def record(event_type):
        async def handler(payload):
            seen.append(event_type)

        return handler

    for event_type in (
        WORKSPACE_RUN_STARTED,
        WORKSPACE_APPLICATION_STATUS,
        WORKSPACE_APPLICATION_RESULT,
        WORKSPACE_RUN_FINISHED,
        WORKSPACE_STATUS_CHANGED,
    ):
        await bus.subscribe(event_type, await record(event_type))

    await service.start_default_workspace()

    assert WORKSPACE_RUN_STARTED in seen
    assert WORKSPACE_APPLICATION_STATUS in seen
    assert WORKSPACE_APPLICATION_RESULT in seen
    assert WORKSPACE_RUN_FINISHED in seen
    assert WORKSPACE_STATUS_CHANGED in seen
    assert seen.index(WORKSPACE_RUN_STARTED) < seen.index(WORKSPACE_RUN_FINISHED)


@pytest.mark.asyncio
async def test_run_cancelled_event_published_instead_of_finished(service_bundle) -> None:
    service, controller, bus, _registry = service_bundle
    controller.hold_for = "vscode"
    cancelled_events: list[dict] = []
    finished_events: list[dict] = []

    async def on_cancelled(payload):
        cancelled_events.append(payload)

    async def on_finished(payload):
        finished_events.append(payload)

    await bus.subscribe(WORKSPACE_RUN_CANCELLED, on_cancelled)
    await bus.subscribe(WORKSPACE_RUN_FINISHED, on_finished)

    task = asyncio.create_task(service.start_default_workspace())
    await asyncio.wait_for(controller.entered_hold.wait(), timeout=2.0)
    controller.hold_event.set()
    await service.cancel()
    await task

    assert len(cancelled_events) == 1
    assert len(finished_events) == 0


@pytest.mark.asyncio
async def test_get_status_reflects_registry_counts(service_bundle) -> None:
    service, _controller, _bus, _registry = service_bundle
    status = service.get_status()
    assert status.total_configured == 3
    assert status.total_enabled == 3
    assert status.enabled is True


@pytest.mark.asyncio
async def test_list_applications_uses_probe(service_bundle) -> None:
    service, _controller, _bus, _registry = service_bundle
    views = service.list_applications()
    assert len(views) == 3
    assert all(v.resolved is True for v in views)


@pytest.mark.asyncio
async def test_open_application_delegates_to_controller(service_bundle) -> None:
    service, controller, _bus, _registry = service_bundle
    result = await service.open_application("vscode")
    assert result.application_id == "vscode"
    assert controller.calls == ["vscode"]


@pytest.mark.asyncio
async def test_open_application_unknown_id_raises_keyerror(service_bundle) -> None:
    service, _controller, _bus, _registry = service_bundle
    with pytest.raises(KeyError):
        await service.open_application("does_not_exist")


@pytest.mark.asyncio
async def test_focus_application_delegates_to_controller(service_bundle) -> None:
    service, _controller, _bus, _registry = service_bundle
    result = await service.focus_application("vscode")
    assert result.result == "FOCUSED"


@pytest.mark.asyncio
async def test_refresh_reloads_registry(service_bundle, tmp_path: Path) -> None:
    service, _controller, _bus, registry = service_bundle
    smaller = json.loads(json.dumps(SAMPLE_CONFIG))
    smaller["applications"] = smaller["applications"][:1]
    registry.config_path.write_text(json.dumps(smaller), encoding="utf-8")

    status = service.refresh()
    assert status.total_configured == 1


@pytest.mark.asyncio
async def test_workspace_disabled_short_circuits(tmp_path: Path) -> None:
    settings = Settings(environment="development", workspace_enabled=False)
    config_path = write_config(tmp_path, SAMPLE_CONFIG)
    registry = AppRegistry(settings=settings, config_path=config_path)
    controller = FakeApplicationController()
    service = WorkspaceService(
        settings=settings,
        event_bus=EventBus(),
        app_registry=registry,
        application_controller=controller,
    )
    status = await service.start_default_workspace()
    assert controller.calls == []
    assert status.status == WorkspaceServiceStatus.IDLE
