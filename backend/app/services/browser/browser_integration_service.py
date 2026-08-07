"""Browser integration service — session tracking + optional CDP."""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from typing import Callable

from app.core.config import Settings
from app.core.events import (
    BROWSER_DESTINATION_FOCUSED,
    BROWSER_DESTINATION_OPENED,
    BROWSER_DESTINATION_UNAVAILABLE,
    BROWSER_STATUS_CHANGED,
    EventBus,
)
from app.models.browser import (
    BrowserActionResult,
    BrowserDestinationStatus,
    BrowserIntegrationMode,
    BrowserIntegrationStatus,
    BrowserStatusResponse,
)
from app.services.browser.browser_destination_registry import BrowserDestinationRegistry
from app.services.browser.chrome_cdp_provider import ChromeCdpProvider
from app.services.browser.session_browser_provider import SessionBrowserProvider

logger = logging.getLogger(__name__)

ChromeLauncher = Callable[[str], None]


class BrowserIntegrationService:
    def __init__(
        self,
        settings: Settings,
        *,
        event_bus: EventBus | None = None,
        registry: BrowserDestinationRegistry | None = None,
        session: SessionBrowserProvider | None = None,
        cdp: ChromeCdpProvider | None = None,
        chrome_launcher: ChromeLauncher | None = None,
        focus_chrome: Callable[[], bool] | None = None,
    ) -> None:
        self._settings = settings
        self._bus = event_bus
        self._registry = registry or BrowserDestinationRegistry(
            dashboard_url=settings.frontend_origin.rstrip("/") + "/",
            gmail_url=settings.gmail_url,
            news_url=settings.news_url,
        )
        self._session = session or SessionBrowserProvider()
        self._cdp = cdp or ChromeCdpProvider(
            host=settings.browser_cdp_host,
            port=settings.browser_cdp_port,
            timeout_seconds=settings.browser_cdp_timeout_seconds,
            registry=self._registry,
            enabled=settings.browser_cdp_enabled,
        )
        self._chrome_launcher = chrome_launcher
        self._focus_chrome = focus_chrome
        self._status = BrowserIntegrationStatus.DISABLED

    def bind(self, event_bus: EventBus | None) -> None:
        self._bus = event_bus

    def set_chrome_launcher(self, launcher: ChromeLauncher | None) -> None:
        self._chrome_launcher = launcher

    def set_focus_chrome(self, handler: Callable[[], bool] | None) -> None:
        self._focus_chrome = handler

    async def on_startup(self) -> None:
        if not self._settings.browser_integration_enabled:
            self._status = BrowserIntegrationStatus.DISABLED
        elif self._settings.browser_cdp_enabled:
            if not self._cdp.validate_host():
                self._status = BrowserIntegrationStatus.ERROR
            elif self._cdp.available():
                self._status = BrowserIntegrationStatus.CONNECTED
            else:
                self._status = BrowserIntegrationStatus.DEGRADED
        else:
            self._status = BrowserIntegrationStatus.CONNECTED
        await self._publish_status()

    async def shutdown(self) -> None:
        self._status = BrowserIntegrationStatus.DISABLED

    def get_status(self) -> BrowserStatusResponse:
        mode = BrowserIntegrationMode.CDP if self._settings.browser_cdp_enabled else BrowserIntegrationMode.SESSION
        exact = bool(
            self._settings.browser_cdp_enabled
            and self._cdp.validate_host()
            and self._status == BrowserIntegrationStatus.CONNECTED
        )
        reason = None
        if self._settings.browser_cdp_enabled and not exact:
            reason = "Exact browser-tab switching unavailable"
        return BrowserStatusResponse(
            enabled=self._settings.browser_integration_enabled,
            status=self._status,
            mode=mode,
            cdp_enabled=self._settings.browser_cdp_enabled,
            exact_tab_focus_available=exact,
            reason=reason,
        )

    def list_destinations(self) -> list[BrowserDestinationStatus]:
        exact = self.get_status().exact_tab_focus_available
        cdp_tabs = {dest_id: tab for dest_id, tab in self._cdp.list_approved_tabs()} if exact else {}
        results: list[BrowserDestinationStatus] = []
        for dest in self._registry.list():
            session = self._session.get(dest.id)
            known = bool(session and session.known_open) or dest.id in cdp_tabs
            results.append(
                BrowserDestinationStatus(
                    id=dest.id,
                    display_name=dest.display_name,
                    known_open=known,
                    exact_focus_available=exact and dest.id in cdp_tabs,
                    url=dest.url,
                    last_opened_at=session.opened_at if session else None,
                    last_focused_at=session.last_requested_at if session else None,
                )
            )
        return results

    async def open_destination(self, destination_id: str) -> BrowserActionResult:
        dest = self._registry.get(destination_id)
        if dest is None:
            return BrowserActionResult(
                destination_id=destination_id,
                action="OPEN",
                result="REJECTED",
                error="Unknown destination",
            )
        # Prefer CDP activate if already open
        if self.get_status().exact_tab_focus_available:
            tab = self._cdp.find_destination_tab(destination_id)
            if tab and self._cdp.activate_tab(tab.tab_id):
                self._session.mark_opened(destination_id, dest.url)
                await self._publish(BROWSER_DESTINATION_FOCUSED, {"id": destination_id})
                return BrowserActionResult(
                    destination_id=destination_id,
                    action="OPEN",
                    result="FOCUSED",
                    exact_focus=True,
                )
        self._launch_url(dest.url)
        self._session.mark_opened(destination_id, dest.url)
        await self._publish(BROWSER_DESTINATION_OPENED, {"id": destination_id})
        return BrowserActionResult(
            destination_id=destination_id,
            action="OPEN",
            result="OPENED",
            exact_focus=False,
        )

    async def focus_destination(self, destination_id: str) -> BrowserActionResult:
        dest = self._registry.get(destination_id)
        if dest is None:
            return BrowserActionResult(
                destination_id=destination_id,
                action="FOCUS",
                result="REJECTED",
                error="Unknown destination",
            )
        if self.get_status().exact_tab_focus_available:
            tab = self._cdp.find_destination_tab(destination_id)
            if tab and self._cdp.activate_tab(tab.tab_id):
                self._session.mark_focused(destination_id)
                await self._publish(BROWSER_DESTINATION_FOCUSED, {"id": destination_id})
                return BrowserActionResult(
                    destination_id=destination_id,
                    action="FOCUS",
                    result="FOCUSED",
                    exact_focus=True,
                )
        # Session fallback: focus Chrome window only
        focused = False
        if self._focus_chrome:
            try:
                focused = bool(self._focus_chrome())
            except Exception:
                focused = False
        session = self._session.get(destination_id)
        if not session:
            await self._publish(
                BROWSER_DESTINATION_UNAVAILABLE,
                {"id": destination_id, "reason": "Not opened in this session"},
            )
            return BrowserActionResult(
                destination_id=destination_id,
                action="FOCUS",
                result="FOCUS_LIMITED",
                exact_focus=False,
                error="Exact tab focus unavailable; Chrome focus attempted"
                if focused
                else "Destination not known open",
            )
        self._session.mark_focused(destination_id)
        await self._publish(BROWSER_DESTINATION_FOCUSED, {"id": destination_id, "exact": False})
        return BrowserActionResult(
            destination_id=destination_id,
            action="FOCUS",
            result="FOCUS_LIMITED",
            exact_focus=False,
            error="Exact tab focus unavailable",
        )

    async def retry(self) -> BrowserStatusResponse:
        await self.on_startup()
        return self.get_status()

    def _launch_url(self, url: str) -> None:
        if self._chrome_launcher:
            self._chrome_launcher(url)
            return
        # Safe fallback: start Chrome with URL (no shell)
        try:
            subprocess.Popen(["chrome.exe", url], shell=False)  # noqa: S603
        except Exception:
            try:
                subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)  # noqa: S603
            except Exception:
                logger.exception("Failed to open browser URL")

    async def _publish_status(self) -> None:
        await self._publish(BROWSER_STATUS_CHANGED, self.get_status().model_dump(mode="json"))

    async def _publish(self, event: str, payload: dict) -> None:
        if self._bus is None:
            return
        await self._bus.publish(event, payload)
