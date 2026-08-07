"""Central window inventory for approved applications."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from app.core.config import Settings
from app.core.events import (
    WINDOWS_FOREGROUND_CHANGED,
    WINDOWS_INVENTORY_CHANGED,
    EventBus,
)
from app.models.application import ApplicationDefinition
from app.models.window import (
    ApplicationWindowGroup,
    SafeWindowRecord,
    WindowFocusResult,
    WindowInventorySnapshot,
    WindowTitleMode,
)
from app.services.windows.opaque_ids import OpaqueWindowIdStore
from app.services.windows.recent_window_tracker import RecentWindowTracker
from app.services.windows.window_classifier import InventoryWin32Api, is_useful_top_level_window
from app.services.windows.window_switcher import WindowSwitcher
from app.services.windows.window_title_policy import sanitize_window_title
from app.services.workspace.process_manager import ProcessManager

logger = logging.getLogger(__name__)

AppResolver = Callable[[], list[ApplicationDefinition]]


class WindowInventoryService:
    def __init__(
        self,
        settings: Settings,
        *,
        event_bus: EventBus | None = None,
        api: InventoryWin32Api | None = None,
        process_manager: ProcessManager | None = None,
        app_resolver: AppResolver | None = None,
        store: OpaqueWindowIdStore | None = None,
        recent: RecentWindowTracker | None = None,
    ) -> None:
        self._settings = settings
        self._bus = event_bus
        self._api = api
        self._processes = process_manager or ProcessManager()
        self._app_resolver = app_resolver or (lambda: [])
        self._store = store or OpaqueWindowIdStore()
        self._recent = recent or RecentWindowTracker(limit=settings.window_recent_limit)
        self._switcher = WindowSwitcher(api=self._api, store=self._store)
        self._snapshot = WindowInventorySnapshot(available=False, reason="DATA PENDING")
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._refresh_requested = False
        self._last_fingerprint: str | None = None
        self._last_foreground_id: str | None = None
        self._display_names: dict[str, str] = {}

    def bind(self, event_bus: EventBus | None) -> None:
        self._bus = event_bus

    def set_api(self, api: InventoryWin32Api | None) -> None:
        self._api = api
        self._switcher = WindowSwitcher(api=api, store=self._store)

    def set_app_resolver(self, resolver: AppResolver) -> None:
        self._app_resolver = resolver

    def get_snapshot(self) -> WindowInventorySnapshot:
        return self._snapshot

    def get_recent(self) -> list[Any]:
        return self._recent.list()

    def get_binding(self, window_id: str):
        return self._store.get(window_id)

    async def on_startup(self) -> None:
        await self.start()

    async def start(self) -> None:
        async with self._lock:
            if not self._settings.window_inventory_enabled:
                self._snapshot = WindowInventorySnapshot(
                    available=False, reason="Window inventory disabled"
                )
                return
            if self._task and not self._task.done():
                return
            if self._api is None:
                from app.services.windows.inventory_api import try_create_inventory_api

                self._api = try_create_inventory_api()
                self._switcher = WindowSwitcher(api=self._api, store=self._store)
            await self.refresh_now()
            self._task = asyncio.create_task(self._loop(), name="window-inventory")
            logger.info("Window inventory started")

    async def stop(self) -> None:
        async with self._lock:
            task = self._task
            self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("Window inventory stopped")

    async def shutdown(self) -> None:
        await self.stop()
        self._store.clear()

    async def request_refresh(self) -> WindowInventorySnapshot:
        self._refresh_requested = True
        return self._snapshot

    async def refresh_now(self) -> WindowInventorySnapshot:
        snapshot, changed, fg_changed, fg_payload = await asyncio.to_thread(self._collect)
        if self._bus is not None:
            if changed:
                await self._bus.publish(
                    WINDOWS_INVENTORY_CHANGED,
                    snapshot.model_dump(mode="json"),
                )
            if fg_changed and fg_payload:
                await self._bus.publish(WINDOWS_FOREGROUND_CHANGED, fg_payload)
        return snapshot

    def focus_window(self, window_id: str) -> WindowFocusResult:
        result = self._switcher.focus(window_id)
        if result.result.value in {"FOCUSED", "RESTORED", "RUNNING_FOCUS_LIMITED"}:
            binding = self._store.get(window_id)
            if binding:
                name = self._display_names.get(binding.application_id, binding.application_id)
                title = sanitize_window_title(
                    application_id=binding.application_id,
                    raw_title=binding.raw_title,
                    display_name=name,
                    mode=self._title_mode(),
                    allow_full=self._allow_full_titles(),
                )
                self._recent.record(
                    window_id=window_id,
                    application_id=binding.application_id,
                    display_name=name,
                    display_title=title,
                )
        return result

    def restore_window(self, window_id: str) -> WindowFocusResult:
        return self._switcher.restore(window_id)

    def _title_mode(self) -> WindowTitleMode:
        raw = (self._settings.window_title_mode or "SAFE").upper()
        try:
            return WindowTitleMode(raw)
        except ValueError:
            return WindowTitleMode.SAFE

    def _allow_full_titles(self) -> bool:
        return bool(
            self._settings.window_debug_full_titles and self._settings.is_development()
        )

    async def _loop(self) -> None:
        interval = self._settings.window_inventory_interval_seconds
        try:
            while True:
                self._refresh_requested = False
                await self.refresh_now()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise

    def _collect(
        self,
    ) -> tuple[WindowInventorySnapshot, bool, bool, dict[str, Any] | None]:
        apps = list(self._app_resolver())
        self._display_names = {app.id: app.display_name for app in apps}
        now = datetime.now(timezone.utc)
        if self._api is None:
            self._snapshot = WindowInventorySnapshot(
                available=False,
                reason="Window API unavailable",
                collected_at=now,
            )
            return self._snapshot, True, False, None

        try:
            foreground = int(self._api.get_foreground_window() or 0)
        except Exception:
            foreground = 0

        app_pids: dict[str, set[int]] = {app.id: set() for app in apps if app.enabled}
        for app in apps:
            if not app.enabled:
                continue
            found = self._processes.find_by_names(app.process_names)
            for proc in found:
                app_pids[app.id].add(int(proc.pid))

        live_hwnds: set[int] = set()
        windows_by_app: dict[str, list[SafeWindowRecord]] = {
            app.id: [] for app in apps if app.enabled
        }

        try:
            handles = self._api.enum_windows()
        except Exception:
            logger.exception("Window enumeration failed")
            handles = []

        for hwnd in handles:
            try:
                if not is_useful_top_level_window(self._api, hwnd):
                    continue
                pid = int(self._api.get_pid_for_window(hwnd) or 0)
                if pid <= 0:
                    continue
                claimants = [app_id for app_id, pids in app_pids.items() if pid in pids]
                if not claimants:
                    continue
                raw_title = self._api.get_window_text(hwnd) or ""
                app_id = self._pick_application(claimants, apps, raw_title)
                if app_id is None:
                    continue
                live_hwnds.add(hwnd)
                binding = self._store.upsert(
                    hwnd=hwnd,
                    application_id=app_id,
                    process_id=pid,
                    raw_title=raw_title,
                )
                display_name = self._display_names.get(app_id, app_id)
                display_title = sanitize_window_title(
                    application_id=app_id,
                    raw_title=raw_title,
                    display_name=display_name,
                    mode=self._title_mode(),
                    allow_full=self._allow_full_titles(),
                )
                is_fg = hwnd == foreground
                record = SafeWindowRecord(
                    window_id=binding.window_id,
                    application_id=app_id,
                    process_id=pid,
                    display_title=display_title,
                    visible=bool(self._api.is_window_visible(hwnd)),
                    minimized=bool(self._api.is_iconic(hwnd)),
                    foreground=is_fg,
                    focusable=True,
                    first_seen_at=binding.first_seen_at,
                    last_seen_at=binding.last_seen_at,
                    last_jarvis_focus_at=binding.last_jarvis_focus_at,
                )
                windows_by_app.setdefault(app_id, []).append(record)
                if is_fg:
                    self._recent.record(
                        window_id=binding.window_id,
                        application_id=app_id,
                        display_name=display_name,
                        display_title=display_title,
                        at=now,
                    )
            except Exception:
                continue

        self._store.prune_missing(live_hwnds)
        valid_ids = {rec.window_id for records in windows_by_app.values() for rec in records}
        self._recent.prune(valid_ids)

        groups: list[ApplicationWindowGroup] = []
        total_windows = 0
        running = 0
        fg_app = None
        fg_win = None

        for app in sorted(
            apps,
            key=lambda a: (not bool(getattr(a, "favourite", False)), a.order, a.id),
        ):
            if not app.enabled:
                continue
            wins = windows_by_app.get(app.id, [])
            is_running = bool(app_pids.get(app.id)) or bool(wins)
            is_fg = any(w.foreground for w in wins)
            if is_fg:
                fg_app = app.id
                fg_win = next((w.window_id for w in wins if w.foreground), None)
            if is_running:
                running += 1
            total_windows += len(wins)
            groups.append(
                ApplicationWindowGroup(
                    application_id=app.id,
                    display_name=app.display_name,
                    running=is_running,
                    window_count=len(wins),
                    foreground=is_fg,
                    favourite=bool(getattr(app, "favourite", False)),
                    allow_preview=bool(getattr(app, "allow_preview", False)),
                    windows=wins,
                )
            )

        snapshot = WindowInventorySnapshot(
            applications=groups,
            total_windows=total_windows,
            running_applications=running,
            foreground_application_id=fg_app,
            foreground_window_id=fg_win,
            collected_at=now,
            available=True,
        )
        fingerprint = self._fingerprint(snapshot)
        changed = fingerprint != self._last_fingerprint
        fg_changed = fg_win != self._last_foreground_id
        self._snapshot = snapshot
        self._last_fingerprint = fingerprint
        self._last_foreground_id = fg_win
        fg_payload = (
            {"window_id": fg_win, "application_id": fg_app} if fg_changed and fg_win else None
        )
        return snapshot, changed, fg_changed, fg_payload

    def _pick_application(
        self,
        claimants: list[str],
        apps: list[ApplicationDefinition],
        raw_title: str,
    ) -> str | None:
        if len(claimants) == 1:
            return claimants[0]
        lower = raw_title.lower()
        by_id = {app.id: app for app in apps}
        if "gmail" in claimants and ("gmail" in lower or "inbox" in lower):
            return "gmail"
        if "news" in claimants and ("news" in lower or "google news" in lower):
            return "news"
        for preferred in ("chrome", "vscode", "teams", "whatsapp", "spotify"):
            if preferred in claimants:
                app = by_id.get(preferred)
                if app is None:
                    continue
                patterns = [p.lower() for p in app.window_title_patterns]
                if not patterns or any(p in lower for p in patterns):
                    return preferred
        return claimants[0]

    @staticmethod
    def _fingerprint(snapshot: WindowInventorySnapshot) -> str:
        parts: list[str] = []
        for app in snapshot.applications:
            parts.append(f"{app.application_id}:{app.window_count}:{app.foreground}")
            for win in app.windows:
                parts.append(
                    f"{win.window_id}:{win.minimized}:{win.foreground}:{win.display_title}"
                )
        return "|".join(parts)
