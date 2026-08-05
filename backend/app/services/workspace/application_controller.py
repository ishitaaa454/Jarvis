"""Per-application open/focus orchestration.

``open_one`` implements: check running -> check window -> restore/focus if
already running, otherwise launch (executable/url/uri/start_app) -> poll for
a window -> build an ApplicationActionResult. Focus denial is treated as a
*limited success*, never a failure. No full command lines are ever placed on
the result object that gets returned to the API/websocket layer.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Awaitable, Callable, Protocol

from app.core.config import Settings
from app.models.application import (
    ApplicationActionResult,
    ApplicationActionStatus,
    ApplicationDefinition,
    LaunchType,
)
from app.services.workspace.browser_controller import BrowserController
from app.services.workspace.executable_resolver import ExecutableResolver
from app.services.workspace.process_manager import ProcessInfo, ProcessManager
from app.services.workspace.start_app_resolver import StartAppResolver
from app.services.workspace.window_manager import WindowInfo, WindowManager

logger = logging.getLogger(__name__)

StatusCallback = Callable[[ApplicationActionStatus, dict], Awaitable[None]]


class ApplicationLaunchError(Exception):
    """Raised internally when a launch attempt fails; message must be safe to expose."""


class AppLauncher(Protocol):
    def launch_executable(self, path: Path, args: list[str]) -> int: ...

    def launch_uri(self, uri: str) -> None: ...

    def launch_start_app(self, app_id: str) -> None: ...


class DefaultAppLauncher:
    """Real launcher used in production. Never uses shell=True."""

    def launch_executable(self, path: Path, args: list[str]) -> int:
        proc = subprocess.Popen([str(path), *args], shell=False)
        return proc.pid

    def launch_uri(self, uri: str) -> None:
        # os.startfile invokes ShellExecute directly; it does not go through cmd.exe.
        startfile = getattr(os, "startfile", None)
        if startfile is None:
            raise ApplicationLaunchError("URI launching is not supported on this platform")
        startfile(uri)

    def launch_start_app(self, app_id: str) -> None:
        subprocess.Popen(
            ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
            shell=False,
        )


class ApplicationController:
    def __init__(
        self,
        *,
        settings: Settings,
        process_manager: ProcessManager,
        window_manager: WindowManager,
        executable_resolver: ExecutableResolver,
        start_app_resolver: StartAppResolver,
        browser_controller: BrowserController,
        launcher: AppLauncher | None = None,
    ) -> None:
        self._settings = settings
        self._process_manager = process_manager
        self._window_manager = window_manager
        self._executable_resolver = executable_resolver
        self._start_app_resolver = start_app_resolver
        self._browser_controller = browser_controller
        self._launcher = launcher or DefaultAppLauncher()

    async def open_one(
        self,
        app: ApplicationDefinition,
        *,
        on_status: StatusCallback | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> ApplicationActionResult:
        started = time.monotonic()

        def elapsed_ms() -> int:
            return int((time.monotonic() - started) * 1000)

        await self._emit(on_status, ApplicationActionStatus.CHECKING)

        pids = self._find_pids(app)
        running = bool(pids)
        window = self._find_window(app, pids) if running else None
        window_found = window is not None

        if running:
            return await self._handle_already_running(
                app, pids, window, window_found, on_status, elapsed_ms
            )

        if cancel_event is not None and cancel_event.is_set():
            return self._build_result(app, status=ApplicationActionStatus.CANCELLED, duration_ms=elapsed_ms())

        try:
            await self._launch(app, on_status=on_status)
        except ApplicationLaunchError as exc:
            await self._emit(on_status, ApplicationActionStatus.FAILED)
            return self._build_result(
                app,
                status=ApplicationActionStatus.FAILED,
                duration_ms=elapsed_ms(),
                error=str(exc),
            )

        await self._emit(on_status, ApplicationActionStatus.WAITING_FOR_STARTUP)
        window = await self._await_window(app, cancel_event=cancel_event)

        if cancel_event is not None and cancel_event.is_set():
            return self._build_result(app, status=ApplicationActionStatus.CANCELLED, duration_ms=elapsed_ms())

        window_found = window is not None
        focus_succeeded = False
        if window_found and app.request_focus_on_launch:
            focus_succeeded = self._window_manager.focus(window)

        pids_after = self._find_pids(app)
        status = ApplicationActionStatus.READY
        await self._emit(on_status, status)
        return ApplicationActionResult(
            application_id=app.id,
            display_name=app.display_name,
            requested_action="open",
            result="LAUNCHED",
            running=True,
            window_found=window_found,
            focus_requested=app.request_focus_on_launch,
            focus_succeeded=focus_succeeded,
            process_id=pids_after[0].pid if pids_after else None,
            duration_ms=elapsed_ms(),
            status=status,
        )

    async def focus_one(self, app: ApplicationDefinition) -> ApplicationActionResult:
        started = time.monotonic()
        pids = self._find_pids(app)
        running = bool(pids)
        window = self._find_window(app, pids) if running else None
        window_found = window is not None
        focus_succeeded = False

        if window_found and window is not None:
            self._window_manager.restore(window)
            focus_succeeded = self._window_manager.focus(window)

        if not running:
            result_label = "NOT_RUNNING"
            status = ApplicationActionStatus.FAILED
        elif not window_found:
            result_label = "WINDOW_NOT_FOUND"
            status = ApplicationActionStatus.READY
        elif focus_succeeded:
            result_label = "FOCUSED"
            status = ApplicationActionStatus.READY
        else:
            # Focus denial is a limited success, not a failure.
            result_label = "FOCUS_DENIED"
            status = ApplicationActionStatus.READY

        return ApplicationActionResult(
            application_id=app.id,
            display_name=app.display_name,
            requested_action="focus",
            result=result_label,
            running=running,
            window_found=window_found,
            focus_requested=True,
            focus_succeeded=focus_succeeded,
            process_id=pids[0].pid if pids else None,
            duration_ms=int((time.monotonic() - started) * 1000),
            status=status,
        )

    def reset_browser_session(self) -> None:
        """Clear per-run URL dedupe state. Call once at the start of each run."""
        self._browser_controller.reset_session()

    def probe(self, app: ApplicationDefinition) -> tuple[bool, bool, bool]:
        """Return (resolved, running, window_found) without launching anything."""
        resolved = True
        if app.launch_type == LaunchType.EXECUTABLE:
            resolved = (
                self._executable_resolver.resolve(
                    configured_path=app.configured_path,
                    candidates=app.executable_candidates,
                )
                is not None
            )
        elif app.launch_type == LaunchType.START_APP:
            resolved = bool(app.start_app_name) and (
                self._start_app_resolver.resolve(app.start_app_name) is not None
            )
        elif app.launch_type in (LaunchType.URL, LaunchType.BROWSER_URL):
            resolved = bool(app.url)
        elif app.launch_type == LaunchType.URI:
            resolved = bool(app.uri)

        pids = self._find_pids(app)
        running = bool(pids)
        window = self._find_window(app, pids) if running else None
        return resolved, running, window is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _handle_already_running(
        self,
        app: ApplicationDefinition,
        pids: list[ProcessInfo],
        window: WindowInfo | None,
        window_found: bool,
        on_status: StatusCallback | None,
        elapsed_ms: Callable[[], int],
    ) -> ApplicationActionResult:
        focus_requested = False
        focus_succeeded = False

        if window_found and window is not None and app.focus_existing and self._settings.workspace_focus_existing:
            focus_requested = True
            await self._emit(on_status, ApplicationActionStatus.RESTORING)
            self._window_manager.restore(window)
            await self._emit(on_status, ApplicationActionStatus.FOCUSING)
            focus_succeeded = self._window_manager.focus(window)
            if not focus_succeeded:
                logger.info("Focus denied for %s (treated as limited success)", app.id)

        status = ApplicationActionStatus.READY
        await self._emit(on_status, status)
        return ApplicationActionResult(
            application_id=app.id,
            display_name=app.display_name,
            requested_action="open",
            result="ALREADY_RUNNING",
            running=True,
            window_found=window_found,
            focus_requested=focus_requested,
            focus_succeeded=focus_succeeded,
            process_id=pids[0].pid if pids else None,
            duration_ms=elapsed_ms(),
            status=status,
        )

    def _build_result(
        self,
        app: ApplicationDefinition,
        *,
        status: ApplicationActionStatus,
        duration_ms: int,
        error: str | None = None,
    ) -> ApplicationActionResult:
        result_label = "CANCELLED" if status == ApplicationActionStatus.CANCELLED else "FAILED"
        return ApplicationActionResult(
            application_id=app.id,
            display_name=app.display_name,
            requested_action="open",
            result=result_label,
            running=False,
            window_found=False,
            duration_ms=duration_ms,
            error=error,
            status=status,
        )

    async def _emit(
        self,
        on_status: StatusCallback | None,
        status: ApplicationActionStatus,
        **extra: object,
    ) -> None:
        if on_status is None:
            return
        try:
            await on_status(status, extra)
        except Exception:
            logger.exception("Workspace status callback failed")

    def _find_pids(self, app: ApplicationDefinition) -> list[ProcessInfo]:
        if not app.process_names:
            return []
        return self._process_manager.find_by_names(app.process_names)

    def _find_window(
        self, app: ApplicationDefinition, pids: list[ProcessInfo]
    ) -> WindowInfo | None:
        if not pids:
            return None
        pid_values = [p.pid for p in pids]
        windows = self._window_manager.find_windows_for_pids(pid_values, app.window_title_patterns)
        return windows[0] if windows else None

    async def _launch(self, app: ApplicationDefinition, *, on_status: StatusCallback | None) -> None:
        await self._emit(on_status, ApplicationActionStatus.LAUNCHING)
        try:
            if app.launch_type == LaunchType.EXECUTABLE:
                await self._launch_executable(app)
            elif app.launch_type in (LaunchType.URL, LaunchType.BROWSER_URL):
                await self._launch_url(app, on_status=on_status)
            elif app.launch_type == LaunchType.URI:
                await self._launch_uri(app, on_status=on_status)
            elif app.launch_type == LaunchType.START_APP:
                await self._launch_start_app(app)
            else:
                raise ApplicationLaunchError(f"Unsupported launch type: {app.launch_type}")
        except ApplicationLaunchError:
            raise
        except Exception as exc:
            logger.exception("Launch failed for application id=%s", app.id)
            raise ApplicationLaunchError("Launch failed unexpectedly") from exc

        delay_s = app.startup_delay_ms / 1000.0
        if delay_s > 0:
            await asyncio.sleep(delay_s)

    async def _launch_executable(self, app: ApplicationDefinition) -> None:
        path = self._executable_resolver.resolve(
            configured_path=app.configured_path,
            candidates=app.executable_candidates,
        )
        if path is None:
            if self._settings.workspace_allow_start_app_launch and app.start_app_name:
                await self._launch_start_app(app)
                return
            raise ApplicationLaunchError("Executable could not be resolved")
        await asyncio.to_thread(self._launcher.launch_executable, path, list(app.launch_arguments))

    async def _launch_url(self, app: ApplicationDefinition, *, on_status: StatusCallback | None) -> None:
        if not self._settings.workspace_allow_url_launch:
            raise ApplicationLaunchError("URL launches are disabled by configuration")
        if not app.url:
            raise ApplicationLaunchError("No URL configured")
        await self._emit(on_status, ApplicationActionStatus.OPENING_URL)
        ok, error = await asyncio.to_thread(self._browser_controller.open_url, app.url)
        if not ok:
            raise ApplicationLaunchError(error or "Failed to open URL")

    async def _launch_uri(self, app: ApplicationDefinition, *, on_status: StatusCallback | None) -> None:
        if not self._settings.workspace_allow_uri_launch:
            raise ApplicationLaunchError("URI launches are disabled by configuration")
        if not app.uri:
            raise ApplicationLaunchError("No URI configured")
        await self._emit(on_status, ApplicationActionStatus.OPENING_URI)
        await asyncio.to_thread(self._launcher.launch_uri, app.uri)

    async def _launch_start_app(self, app: ApplicationDefinition) -> None:
        if not self._settings.workspace_allow_start_app_launch:
            raise ApplicationLaunchError("Start app launches are disabled by configuration")
        if not app.start_app_name:
            raise ApplicationLaunchError("No start app name configured")
        start_app = self._start_app_resolver.resolve(app.start_app_name)
        if start_app is None:
            raise ApplicationLaunchError("Start app entry not found")
        await asyncio.to_thread(self._launcher.launch_start_app, start_app.app_id)

    async def _await_window(
        self,
        app: ApplicationDefinition,
        *,
        cancel_event: asyncio.Event | None,
    ) -> WindowInfo | None:
        if not app.process_names:
            return None

        timeout = self._settings.workspace_window_discovery_timeout_seconds
        poll_interval = max(0.05, self._settings.workspace_window_poll_interval_ms / 1000.0)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                return None
            pids = self._find_pids(app)
            if pids:
                window = self._find_window(app, pids)
                if window is not None:
                    return window
            await asyncio.sleep(poll_interval)
        return None
