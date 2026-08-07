"""Sequential workspace launch orchestration: status, events, cancellation.

Owns the single active "workspace run" (never two concurrent runs — a second
``start_default_workspace`` call while one is active raises
``WorkspaceRunConflictError``). Applications are opened one at a time, in
configured order, with a short delay between each. Continues past a failed
application when WORKSPACE_CONTINUE_ON_APPLICATION_ERROR is enabled.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from app.core.config import Settings, get_settings
from app.core.events import (
    WORKSPACE_APPLICATION_RESULT,
    WORKSPACE_APPLICATION_STATUS,
    WORKSPACE_ERROR,
    WORKSPACE_RUN_CANCELLED,
    WORKSPACE_RUN_FINISHED,
    WORKSPACE_RUN_STARTED,
    WORKSPACE_STATUS_CHANGED,
    WORKSPACE_WARNING,
    EventBus,
)
from app.models.application import (
    ApplicationActionResult,
    ApplicationActionStatus,
    ApplicationRuntimeView,
    WorkspaceProgress,
    WorkspaceRunSummary,
    WorkspaceServiceStatus,
    WorkspaceStatusResponse,
    workspace_status_to_ws_payload,
)
from app.services.workspace.app_registry import AppRegistry, AppRegistryError
from app.services.workspace.application_controller import (
    ApplicationController,
    DefaultAppLauncher,
)
from app.services.workspace.browser_controller import BrowserController
from app.services.workspace.executable_resolver import ExecutableResolver
from app.services.workspace.process_manager import ProcessManager
from app.services.workspace.start_app_resolver import StartAppResolver
from app.services.workspace.window_manager import WindowManager
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = {
    WorkspaceServiceStatus.PREPARING,
    WorkspaceServiceStatus.LAUNCHING,
    WorkspaceServiceStatus.CANCELLING,
}


class WorkspaceRunConflictError(Exception):
    """Raised when a workspace launch is requested while one is already active."""


class WorkspaceService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        event_bus: EventBus | None = None,
        app_registry: AppRegistry | None = None,
        application_controller: ApplicationController | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._event_bus = event_bus

        self._registry_error: str | None = None
        self._registry: AppRegistry | None = app_registry
        if self._registry is None:
            try:
                self._registry = AppRegistry(settings=self._settings)
            except AppRegistryError as exc:
                logger.error("Workspace registry failed to load: %s", exc)
                self._registry_error = str(exc)
                self._registry = None

        self._controller = application_controller or self._build_default_controller()

        self._lock = asyncio.Lock()
        self._status = WorkspaceServiceStatus.IDLE
        self._active_run_id: str | None = None
        self._current_application: str | None = None
        self._progress = WorkspaceProgress()
        self._last_run: WorkspaceRunSummary | None = None
        self._last_error: str | None = self._registry_error
        self._cancel_event: asyncio.Event | None = None
        self._run_task: asyncio.Task[WorkspaceStatusResponse] | None = None

    def _build_default_controller(self) -> ApplicationController:
        process_manager = ProcessManager()
        window_manager = WindowManager(debug_titles=self._settings.workspace_debug_window_discovery)
        executable_resolver = ExecutableResolver()
        start_app_resolver = StartAppResolver()
        launcher = DefaultAppLauncher()

        def resolve_chrome():
            return executable_resolver.resolve(
                configured_path=self._settings.chrome_executable_path,
                candidates=["chrome.exe"],
            )

        browser_controller = BrowserController(
            resolve_chrome=resolve_chrome,
            process_manager=process_manager,
            launcher=launcher,
            allow_localhost_http=self._settings.is_development(),
        )

        return ApplicationController(
            settings=self._settings,
            process_manager=process_manager,
            window_manager=window_manager,
            executable_resolver=executable_resolver,
            start_app_resolver=start_app_resolver,
            browser_controller=browser_controller,
            launcher=launcher,
        )

    def bind(self, *, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Status / introspection
    # ------------------------------------------------------------------

    def get_status(self) -> WorkspaceStatusResponse:
        total_configured = len(self._registry.all_applications()) if self._registry else 0
        total_enabled = len(self._registry.enabled_in_order()) if self._registry else 0
        profile = self._registry.profile if self._registry else self._settings.workspace_default_profile
        return WorkspaceStatusResponse(
            enabled=self._settings.workspace_enabled,
            status=self._status,
            active_run_id=self._active_run_id,
            profile=profile,
            total_configured=total_configured,
            total_enabled=total_enabled,
            current_application=self._current_application,
            progress=self._progress,
            last_run=self._last_run,
            last_error=self._last_error,
        )

    def list_applications(self) -> list[ApplicationRuntimeView]:
        if self._registry is None:
            return []
        views: list[ApplicationRuntimeView] = []
        for app in self._registry.all_applications():
            resolved, running, window_found = self._controller.probe(app)
            views.append(
                ApplicationRuntimeView(
                    id=app.id,
                    display_name=app.display_name,
                    enabled=app.enabled,
                    order=app.order,
                    launch_type=app.launch_type,
                    resolved=resolved,
                    running=running,
                    window_found=window_found,
                    status=ApplicationActionStatus.READY if running else ApplicationActionStatus.PENDING,
                    last_result=self._last_result_for(app.id),
                )
            )
        return views

    def _last_result_for(self, app_id: str) -> str | None:
        if self._last_run is None:
            return None
        for result in self._last_run.applications:
            if result.application_id == app_id:
                return result.result
        return None

    def is_running(self) -> bool:
        return self._status in _ACTIVE_STATUSES

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def on_startup(self) -> None:
        logger.info(
            "Workspace service initializing (enabled=%s, start_after_welcome=%s)",
            self._settings.workspace_enabled,
            self._settings.workspace_start_after_welcome,
        )
        await self._publish_status()

    async def shutdown(self) -> None:
        await self.cancel()

    def refresh(self) -> WorkspaceStatusResponse:
        """Reload the application registry from disk."""
        try:
            if self._registry is not None:
                self._registry.reload()
            else:
                self._registry = AppRegistry(settings=self._settings)
            self._registry_error = None
            self._last_error = None
        except AppRegistryError as exc:
            logger.error("Workspace registry reload failed: %s", exc)
            self._registry_error = str(exc)
            self._last_error = str(exc)
        return self.get_status()

    # ------------------------------------------------------------------
    # Run orchestration
    # ------------------------------------------------------------------

    async def start_default_workspace(self) -> WorkspaceStatusResponse:
        async with self._lock:
            if self.is_running():
                raise WorkspaceRunConflictError("A workspace run is already active")

            if not self._settings.workspace_enabled:
                await self._publish(
                    WORKSPACE_WARNING,
                    {"message": "Workspace launching is disabled by configuration"},
                )
                return self.get_status()

            if self._registry is None:
                self._status = WorkspaceServiceStatus.ERROR
                self._last_error = self._registry_error or "Workspace configuration is unavailable"
                await self._publish(WORKSPACE_ERROR, {"message": self._last_error})
                await self._publish_status()
                return self.get_status()

            run_id = uuid.uuid4().hex
            self._active_run_id = run_id
            self._cancel_event = asyncio.Event()
            self._status = WorkspaceServiceStatus.PREPARING
            self._current_application = None
            self._progress = WorkspaceProgress()
            self._last_error = None

        await self._publish_status()

        cancel_event = self._cancel_event
        assert cancel_event is not None
        task = asyncio.create_task(self._run(run_id, cancel_event))
        self._run_task = task
        try:
            return await task
        finally:
            if self._run_task is task:
                self._run_task = None

    async def _run(self, run_id: str, cancel_event: asyncio.Event) -> WorkspaceStatusResponse:
        assert self._registry is not None
        apps = self._registry.enabled_in_order()
        started_at = utc_now()
        results: list[ApplicationActionResult] = []

        reset_browser_session = getattr(self._controller, "reset_browser_session", None)
        if callable(reset_browser_session):
            reset_browser_session()

        await self._publish(
            WORKSPACE_RUN_STARTED,
            {"run_id": run_id, "total": len(apps), "profile": self._registry.profile},
        )

        async with self._lock:
            self._status = WorkspaceServiceStatus.LAUNCHING
            self._progress = WorkspaceProgress(completed=0, total=len(apps))
        await self._publish_status()

        was_cancelled = False
        for index, app in enumerate(apps):
            if cancel_event.is_set():
                was_cancelled = True
                results.append(self._skipped_result(app, cancelled=True))
                continue

            self._current_application = app.id
            await self._publish_status()

            async def on_status(status: ApplicationActionStatus, extra: dict[str, Any]) -> None:
                await self._publish(
                    WORKSPACE_APPLICATION_STATUS,
                    {
                        "run_id": run_id,
                        "application_id": app.id,
                        "display_name": app.display_name,
                        "status": status.value,
                        **extra,
                    },
                )

            try:
                result = await self._controller.open_one(
                    app, on_status=on_status, cancel_event=cancel_event
                )
            except Exception:
                logger.exception("Unhandled error opening application id=%s", app.id)
                result = ApplicationActionResult(
                    application_id=app.id,
                    display_name=app.display_name,
                    requested_action="open",
                    result="FAILED",
                    error="Unexpected error while opening application",
                    status=ApplicationActionStatus.FAILED,
                )
                await self._publish(
                    WORKSPACE_WARNING,
                    {
                        "run_id": run_id,
                        "application_id": app.id,
                        "message": "Unexpected error while opening application",
                    },
                )

            results.append(result)
            self._progress = WorkspaceProgress(completed=index + 1, total=len(apps))
            await self._publish(
                WORKSPACE_APPLICATION_RESULT,
                {"run_id": run_id, **result.model_dump(mode="json")},
            )
            await self._publish_status()

            if (
                result.status == ApplicationActionStatus.FAILED
                and not self._settings.workspace_continue_on_application_error
            ):
                logger.warning(
                    "Stopping workspace run %s after failure (continue_on_error disabled): %s",
                    run_id,
                    app.id,
                )
                for remaining_app in apps[index + 1 :]:
                    results.append(self._skipped_result(remaining_app, cancelled=False))
                break

            if cancel_event.is_set():
                was_cancelled = True
                continue

            if index < len(apps) - 1:
                delay_s = self._settings.workspace_inter_app_delay_ms / 1000.0
                if delay_s > 0:
                    await asyncio.sleep(delay_s)

        self._current_application = None
        finished_at = utc_now()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        successful = sum(
            1 for r in results if r.status == ApplicationActionStatus.READY
        )
        failed = sum(1 for r in results if r.status == ApplicationActionStatus.FAILED)
        skipped = sum(
            1
            for r in results
            if r.status in {ApplicationActionStatus.SKIPPED, ApplicationActionStatus.CANCELLED}
        )

        if was_cancelled or cancel_event.is_set():
            final_status = WorkspaceServiceStatus.CANCELLED
        elif failed == 0:
            final_status = WorkspaceServiceStatus.READY
        elif successful > 0:
            final_status = WorkspaceServiceStatus.PARTIAL_SUCCESS
        else:
            final_status = WorkspaceServiceStatus.ERROR

        summary = WorkspaceRunSummary(
            run_id=run_id,
            status=final_status,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            total_applications=len(apps),
            successful=successful,
            failed=failed,
            skipped=skipped,
            applications=results,
        )

        async with self._lock:
            self._status = final_status
            self._last_run = summary
            self._active_run_id = None
            self._cancel_event = None
            if final_status == WorkspaceServiceStatus.ERROR:
                self._last_error = "All applications failed to open"

        if final_status == WorkspaceServiceStatus.CANCELLED:
            await self._publish(WORKSPACE_RUN_CANCELLED, {"run_id": run_id})
        else:
            await self._publish(
                WORKSPACE_RUN_FINISHED,
                {"run_id": run_id, "status": final_status.value, "summary": summary.model_dump(mode="json")},
            )

        if final_status == WorkspaceServiceStatus.ERROR:
            await self._publish(WORKSPACE_ERROR, {"run_id": run_id, "message": self._last_error})

        await self._publish_status()
        return self.get_status()

    def _skipped_result(self, app, *, cancelled: bool) -> ApplicationActionResult:
        return ApplicationActionResult(
            application_id=app.id,
            display_name=app.display_name,
            requested_action="open",
            result="CANCELLED" if cancelled else "SKIPPED",
            status=ApplicationActionStatus.CANCELLED if cancelled else ApplicationActionStatus.SKIPPED,
        )

    async def cancel(self) -> WorkspaceStatusResponse:
        async with self._lock:
            if not self.is_running():
                return self.get_status()
            self._status = WorkspaceServiceStatus.CANCELLING
            if self._cancel_event is not None:
                self._cancel_event.set()
        await self._publish_status()

        task = self._run_task
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Workspace cancellation timed out waiting for the run task")
            except Exception:
                logger.exception("Error while waiting for workspace run to cancel")
        return self.get_status()

    # ------------------------------------------------------------------
    # Single-application actions (API)
    # ------------------------------------------------------------------

    async def open_application(self, app_id: str) -> ApplicationActionResult:
        app = self._registry.get(app_id) if self._registry else None
        if app is None:
            raise KeyError(app_id)
        return await self._controller.open_one(app)

    async def focus_application(self, app_id: str) -> ApplicationActionResult:
        app = self._registry.get(app_id) if self._registry else None
        if app is None:
            raise KeyError(app_id)
        return await self._controller.focus_one(app)

    def list_application_definitions(self):
        if self._registry is None:
            return []
        return self._registry.all_applications()

    def open_url_via_chrome(self, url: str) -> tuple[bool, str | None]:
        """Open an approved URL through the workspace BrowserController."""
        browser = getattr(self._controller, "_browser_controller", None)
        if browser is None:
            return False, "Browser controller unavailable"
        return browser.open_url(url)

    # ------------------------------------------------------------------
    # Event publishing
    # ------------------------------------------------------------------

    async def _publish_status(self) -> None:
        await self._publish(WORKSPACE_STATUS_CHANGED, workspace_status_to_ws_payload(self.get_status()))

    async def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        await self._event_bus.publish(event_type, payload)
