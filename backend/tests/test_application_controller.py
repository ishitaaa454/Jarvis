"""ApplicationController.open_one/focus_one tests — everything mocked, no real apps."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.config import Settings
from app.models.application import ApplicationActionStatus, ApplicationDefinition, LaunchType
from app.services.workspace.application_controller import ApplicationController
from app.services.workspace.process_manager import ProcessInfo
from app.services.workspace.start_app_resolver import StartApp
from app.services.workspace.window_manager import WindowInfo


class FakeProcessManager:
    def __init__(self, running: dict[str, list[ProcessInfo]] | None = None) -> None:
        self._running = running or {}

    def find_by_names(self, names: list[str]) -> list[ProcessInfo]:
        for name in names:
            if name in self._running:
                return self._running[name]
        return []

    def is_running(self, names: list[str]) -> bool:
        return bool(self.find_by_names(names))

    def set_running(self, name: str, processes: list[ProcessInfo]) -> None:
        self._running[name] = processes


class FakeWindowManager:
    def __init__(self) -> None:
        self.windows: dict[int, WindowInfo] = {}
        self.restore_calls: list[int] = []
        self.focus_calls: list[int] = []
        self.deny_focus = False

    def find_windows_for_pids(self, pids, title_patterns=None):
        return [w for pid, w in self.windows.items() if pid in pids]

    def restore(self, window: WindowInfo) -> bool:
        self.restore_calls.append(window.hwnd)
        return True

    def focus(self, window: WindowInfo) -> bool:
        self.focus_calls.append(window.hwnd)
        return not self.deny_focus


class FakeExecutableResolver:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.calls = 0

    def resolve(self, *, configured_path="", candidates=None):
        self.calls += 1
        return self.path


class FakeStartAppResolver:
    def __init__(self, app: StartApp | None) -> None:
        self.app = app

    def resolve(self, name: str):
        return self.app


class FakeBrowserController:
    def __init__(self, ok: bool = True, error: str | None = None) -> None:
        self.ok = ok
        self.error = error
        self.opened: list[str] = []

    def open_url(self, url: str):
        self.opened.append(url)
        return self.ok, self.error


class FakeLauncher:
    def __init__(self) -> None:
        self.executable_calls: list[tuple[Path, list[str]]] = []
        self.uri_calls: list[str] = []
        self.start_app_calls: list[str] = []
        self.raise_on_executable: Exception | None = None

    def launch_executable(self, path: Path, args: list[str]) -> int:
        if self.raise_on_executable:
            raise self.raise_on_executable
        self.executable_calls.append((path, args))
        return 4242

    def launch_uri(self, uri: str) -> None:
        self.uri_calls.append(uri)

    def launch_start_app(self, app_id: str) -> None:
        self.start_app_calls.append(app_id)


def make_settings(**overrides) -> Settings:
    defaults = dict(
        environment="development",
        workspace_window_discovery_timeout_seconds=0.3,
        workspace_window_poll_interval_ms=50,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def make_app(**overrides) -> ApplicationDefinition:
    defaults = dict(
        id="vscode",
        display_name="Visual Studio Code",
        launch_type=LaunchType.EXECUTABLE,
        executable_candidates=["code.cmd"],
        process_names=["Code.exe"],
        window_title_patterns=["Visual Studio Code"],
        startup_delay_ms=0,
    )
    defaults.update(overrides)
    return ApplicationDefinition(**defaults)


def make_controller(
    *,
    settings=None,
    process_manager=None,
    window_manager=None,
    executable_resolver=None,
    start_app_resolver=None,
    browser_controller=None,
    launcher=None,
) -> ApplicationController:
    return ApplicationController(
        settings=settings or make_settings(),
        process_manager=process_manager or FakeProcessManager(),
        window_manager=window_manager or FakeWindowManager(),
        executable_resolver=executable_resolver or FakeExecutableResolver(Path("C:/fake/code.exe")),
        start_app_resolver=start_app_resolver or FakeStartAppResolver(None),
        browser_controller=browser_controller or FakeBrowserController(),
        launcher=launcher or FakeLauncher(),
    )


@pytest.mark.asyncio
async def test_already_running_focuses_and_returns_ready() -> None:
    app = make_app()
    process_manager = FakeProcessManager({"Code.exe": [ProcessInfo(pid=111, name="Code.exe")]})
    window_manager = FakeWindowManager()
    window_manager.windows[111] = WindowInfo(hwnd=555, pid=111, title="")

    controller = make_controller(process_manager=process_manager, window_manager=window_manager)
    result = await controller.open_one(app)

    assert result.result == "ALREADY_RUNNING"
    assert result.running is True
    assert result.window_found is True
    assert result.focus_requested is True
    assert result.focus_succeeded is True
    assert result.status == ApplicationActionStatus.READY
    assert window_manager.restore_calls == [555]
    assert window_manager.focus_calls == [555]


@pytest.mark.asyncio
async def test_focus_denial_is_limited_success_not_failure() -> None:
    app = make_app()
    process_manager = FakeProcessManager({"Code.exe": [ProcessInfo(pid=111, name="Code.exe")]})
    window_manager = FakeWindowManager()
    window_manager.windows[111] = WindowInfo(hwnd=555, pid=111, title="")
    window_manager.deny_focus = True

    controller = make_controller(process_manager=process_manager, window_manager=window_manager)
    result = await controller.open_one(app)

    assert result.status == ApplicationActionStatus.READY
    assert result.result == "ALREADY_RUNNING"
    assert result.focus_requested is True
    assert result.focus_succeeded is False


@pytest.mark.asyncio
async def test_already_running_without_focus_existing_skips_focus() -> None:
    app = make_app(focus_existing=False)
    process_manager = FakeProcessManager({"Code.exe": [ProcessInfo(pid=111, name="Code.exe")]})
    window_manager = FakeWindowManager()
    window_manager.windows[111] = WindowInfo(hwnd=555, pid=111, title="")

    controller = make_controller(process_manager=process_manager, window_manager=window_manager)
    result = await controller.open_one(app)

    assert result.focus_requested is False
    assert window_manager.focus_calls == []


@pytest.mark.asyncio
async def test_launch_executable_when_not_running() -> None:
    app = make_app()
    process_manager = FakeProcessManager()
    window_manager = FakeWindowManager()
    launcher = FakeLauncher()
    resolver = FakeExecutableResolver(Path("C:/fake/code.exe"))

    controller = make_controller(
        process_manager=process_manager,
        window_manager=window_manager,
        executable_resolver=resolver,
        launcher=launcher,
    )
    result = await controller.open_one(app)

    assert result.result == "LAUNCHED"
    assert result.status == ApplicationActionStatus.READY
    assert launcher.executable_calls == [(Path("C:/fake/code.exe"), [])]


@pytest.mark.asyncio
async def test_launch_executable_unresolved_fails() -> None:
    app = make_app(start_app_name=None)
    controller = make_controller(executable_resolver=FakeExecutableResolver(None))
    result = await controller.open_one(app)

    assert result.status == ApplicationActionStatus.FAILED
    assert result.result == "FAILED"
    assert result.error is not None


@pytest.mark.asyncio
async def test_launch_executable_falls_back_to_start_app_when_unresolved() -> None:
    app = make_app(start_app_name="Visual Studio Code")
    start_app = StartApp(name="Visual Studio Code", app_id="VSCode_AppId!App")
    launcher = FakeLauncher()

    controller = make_controller(
        executable_resolver=FakeExecutableResolver(None),
        start_app_resolver=FakeStartAppResolver(start_app),
        launcher=launcher,
    )
    result = await controller.open_one(app)

    assert result.status == ApplicationActionStatus.READY
    assert launcher.start_app_calls == ["VSCode_AppId!App"]


@pytest.mark.asyncio
async def test_launch_url_success() -> None:
    app = make_app(
        id="gmail",
        launch_type=LaunchType.BROWSER_URL,
        process_names=["chrome.exe"],
        url="https://mail.google.com/",
        executable_candidates=[],
    )
    browser = FakeBrowserController(ok=True)
    controller = make_controller(browser_controller=browser)
    result = await controller.open_one(app)

    assert result.status == ApplicationActionStatus.READY
    assert browser.opened == ["https://mail.google.com/"]


@pytest.mark.asyncio
async def test_launch_url_failure_propagates_as_failed_result() -> None:
    app = make_app(
        id="gmail",
        launch_type=LaunchType.BROWSER_URL,
        process_names=["chrome.exe"],
        url="https://mail.google.com/",
        executable_candidates=[],
    )
    browser = FakeBrowserController(ok=False, error="Chrome executable could not be resolved")
    controller = make_controller(browser_controller=browser)
    result = await controller.open_one(app)

    assert result.status == ApplicationActionStatus.FAILED
    assert result.error == "Chrome executable could not be resolved"


@pytest.mark.asyncio
async def test_url_launch_disabled_by_settings() -> None:
    app = make_app(
        id="gmail",
        launch_type=LaunchType.URL,
        url="https://mail.google.com/",
        executable_candidates=[],
        process_names=[],
    )
    settings = make_settings(workspace_allow_url_launch=False)
    controller = make_controller(settings=settings)
    result = await controller.open_one(app)
    assert result.status == ApplicationActionStatus.FAILED


@pytest.mark.asyncio
async def test_launch_uri_success() -> None:
    app = make_app(
        id="spotify",
        launch_type=LaunchType.URI,
        uri="spotify:",
        executable_candidates=[],
        process_names=["Spotify.exe"],
    )
    launcher = FakeLauncher()
    controller = make_controller(launcher=launcher)
    result = await controller.open_one(app)

    assert result.status == ApplicationActionStatus.READY
    assert launcher.uri_calls == ["spotify:"]


@pytest.mark.asyncio
async def test_uri_launch_disabled_by_settings() -> None:
    app = make_app(
        id="spotify",
        launch_type=LaunchType.URI,
        uri="spotify:",
        executable_candidates=[],
        process_names=[],
    )
    settings = make_settings(workspace_allow_uri_launch=False)
    controller = make_controller(settings=settings)
    result = await controller.open_one(app)
    assert result.status == ApplicationActionStatus.FAILED


@pytest.mark.asyncio
async def test_launch_start_app_success() -> None:
    app = make_app(
        id="teams",
        launch_type=LaunchType.START_APP,
        start_app_name="Microsoft Teams",
        executable_candidates=[],
        process_names=["ms-teams.exe"],
    )
    start_app = StartApp(name="Microsoft Teams", app_id="Teams_AppId!App")
    launcher = FakeLauncher()
    controller = make_controller(
        start_app_resolver=FakeStartAppResolver(start_app),
        launcher=launcher,
    )
    result = await controller.open_one(app)

    assert result.status == ApplicationActionStatus.READY
    assert launcher.start_app_calls == ["Teams_AppId!App"]


@pytest.mark.asyncio
async def test_start_app_not_found_fails() -> None:
    app = make_app(
        id="teams",
        launch_type=LaunchType.START_APP,
        start_app_name="Microsoft Teams",
        executable_candidates=[],
        process_names=[],
    )
    controller = make_controller(start_app_resolver=FakeStartAppResolver(None))
    result = await controller.open_one(app)
    assert result.status == ApplicationActionStatus.FAILED


@pytest.mark.asyncio
async def test_launch_exception_is_caught_and_reported_safely() -> None:
    app = make_app()
    launcher = FakeLauncher()
    launcher.raise_on_executable = RuntimeError("some very sensitive internal detail")
    controller = make_controller(launcher=launcher)
    result = await controller.open_one(app)

    assert result.status == ApplicationActionStatus.FAILED
    assert result.error == "Launch failed unexpectedly"
    assert "sensitive" not in (result.error or "")


@pytest.mark.asyncio
async def test_cancel_before_launch_returns_cancelled() -> None:
    app = make_app()
    controller = make_controller()
    cancel_event = asyncio.Event()
    cancel_event.set()
    result = await controller.open_one(app, cancel_event=cancel_event)
    assert result.status == ApplicationActionStatus.CANCELLED


@pytest.mark.asyncio
async def test_status_callback_receives_progress_events() -> None:
    app = make_app()
    events: list[ApplicationActionStatus] = []

    async def on_status(status, extra):
        events.append(status)

    controller = make_controller()
    await controller.open_one(app, on_status=on_status)

    assert ApplicationActionStatus.CHECKING in events
    assert ApplicationActionStatus.LAUNCHING in events
    assert ApplicationActionStatus.WAITING_FOR_STARTUP in events
    assert ApplicationActionStatus.READY in events


@pytest.mark.asyncio
async def test_status_callback_exception_does_not_break_launch() -> None:
    app = make_app()

    async def bad_callback(status, extra):
        raise RuntimeError("callback exploded")

    controller = make_controller()
    result = await controller.open_one(app, on_status=bad_callback)
    assert result.status == ApplicationActionStatus.READY


@pytest.mark.asyncio
async def test_focus_one_not_running() -> None:
    app = make_app()
    controller = make_controller()
    result = await controller.focus_one(app)
    assert result.running is False
    assert result.result == "NOT_RUNNING"
    assert result.status == ApplicationActionStatus.FAILED


@pytest.mark.asyncio
async def test_focus_one_running_with_window_focuses() -> None:
    app = make_app()
    process_manager = FakeProcessManager({"Code.exe": [ProcessInfo(pid=111, name="Code.exe")]})
    window_manager = FakeWindowManager()
    window_manager.windows[111] = WindowInfo(hwnd=555, pid=111, title="")

    controller = make_controller(process_manager=process_manager, window_manager=window_manager)
    result = await controller.focus_one(app)

    assert result.running is True
    assert result.focus_succeeded is True
    assert result.result == "FOCUSED"


@pytest.mark.asyncio
async def test_focus_one_denial_is_limited_success() -> None:
    app = make_app()
    process_manager = FakeProcessManager({"Code.exe": [ProcessInfo(pid=111, name="Code.exe")]})
    window_manager = FakeWindowManager()
    window_manager.windows[111] = WindowInfo(hwnd=555, pid=111, title="")
    window_manager.deny_focus = True

    controller = make_controller(process_manager=process_manager, window_manager=window_manager)
    result = await controller.focus_one(app)

    assert result.status == ApplicationActionStatus.READY
    assert result.result == "FOCUS_DENIED"


def test_probe_reports_resolution_and_running_state() -> None:
    app = make_app()
    process_manager = FakeProcessManager({"Code.exe": [ProcessInfo(pid=111, name="Code.exe")]})
    window_manager = FakeWindowManager()
    window_manager.windows[111] = WindowInfo(hwnd=555, pid=111, title="")
    controller = make_controller(process_manager=process_manager, window_manager=window_manager)

    resolved, running, window_found = controller.probe(app)
    assert resolved is True
    assert running is True
    assert window_found is True
