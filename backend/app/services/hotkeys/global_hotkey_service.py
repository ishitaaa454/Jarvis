"""Global hotkey registration via Win32 RegisterHotKey (no keylogging)."""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Callable

from app.core.config import Settings
from app.core.events import HOTKEY_STATUS_CHANGED, HOTKEY_TRIGGERED, EventBus
from app.models.hotkey import (
    HotkeyAction,
    HotkeyServiceStatus,
    HotkeyShortcut,
    HotkeyStatusResponse,
)

logger = logging.getLogger(__name__)

# Virtual-key codes
VK_J = 0x4A
VK_SPACE = 0x20
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004

HOTKEY_ID = 0x4A01  # Jarvis show-dashboard

ALLOWED_HOTKEYS = {
    "CTRL+ALT+J": (MOD_CONTROL | MOD_ALT, VK_J, "Ctrl + Alt + J"),
    "CTRL+SHIFT+J": (MOD_CONTROL | MOD_SHIFT, VK_J, "Ctrl + Shift + J"),
    "CTRL+ALT+SPACE": (MOD_CONTROL | MOD_ALT, VK_SPACE, "Ctrl + Alt + Space"),
}


class GlobalHotkeyService:
    def __init__(
        self,
        settings: Settings,
        *,
        event_bus: EventBus | None = None,
        on_show_dashboard: Callable[[], None] | None = None,
    ) -> None:
        self._settings = settings
        self._bus = event_bus
        self._on_show = on_show_dashboard
        self._status = HotkeyServiceStatus.STOPPED
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_triggered: datetime | None = None
        self._conflict: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._registered = False

    def bind(self, event_bus: EventBus | None) -> None:
        self._bus = event_bus

    def set_show_dashboard_handler(self, handler: Callable[[], None] | None) -> None:
        self._on_show = handler

    def get_status(self) -> HotkeyStatusResponse:
        combo = (self._settings.global_hotkey_show_dashboard or "CTRL+ALT+J").upper().replace(" ", "")
        display = ALLOWED_HOTKEYS.get(combo, ALLOWED_HOTKEYS["CTRL+ALT+J"])[2]
        return HotkeyStatusResponse(
            enabled=self._settings.global_hotkey_enabled,
            status=self._status,
            shortcuts=[
                HotkeyShortcut(action=HotkeyAction.SHOW_DASHBOARD, display=display)
            ]
            if self._settings.global_hotkey_enabled
            else [],
            last_triggered_at=self._last_triggered,
            conflict_message=self._conflict,
        )

    async def on_startup(self) -> None:
        await self.start()

    async def start(self) -> None:
        if not self._settings.global_hotkey_enabled:
            self._status = HotkeyServiceStatus.DISABLED
            await self._publish_status()
            return
        if self._thread and self._thread.is_alive():
            return
        self._status = HotkeyServiceStatus.STARTING
        await self._publish_status()
        self._stop.clear()
        self._loop = asyncio.get_running_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="jarvis-hotkey",
            daemon=True,
        )
        self._thread.start()

    async def stop(self) -> None:
        self._status = HotkeyServiceStatus.STOPPING
        await self._publish_status()
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread and thread.is_alive():
            thread.join(timeout=3.0)
        self._registered = False
        self._status = HotkeyServiceStatus.STOPPED
        await self._publish_status()
        logger.info("Global hotkey service stopped")

    async def shutdown(self) -> None:
        await self.stop()

    async def retry(self) -> HotkeyStatusResponse:
        await self.stop()
        await self.start()
        return self.get_status()

    def _run_loop(self) -> None:
        try:
            import win32api
            import win32con
            import win32gui
        except Exception:
            self._status = HotkeyServiceStatus.ERROR
            self._conflict = "pywin32 unavailable"
            self._schedule_status()
            return

        combo = (self._settings.global_hotkey_show_dashboard or "CTRL+ALT+J").upper().replace(" ", "")
        if combo not in ALLOWED_HOTKEYS:
            combo = "CTRL+ALT+J"
        modifiers, vk, _display = ALLOWED_HOTKEYS[combo]

        # Message-only window
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = "JarvisHotkeyWindow"
        wc.hInstance = win32api.GetModuleHandle(None)
        try:
            class_atom = win32gui.RegisterClass(wc)
        except Exception:
            # Already registered from previous start in same process
            class_atom = wc.lpszClassName
        hwnd = win32gui.CreateWindow(
            class_atom,
            "JarvisHotkey",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            wc.hInstance,
            None,
        )
        try:
            ok = win32gui.RegisterHotKey(hwnd, HOTKEY_ID, modifiers, vk)
        except Exception as exc:
            self._status = HotkeyServiceStatus.CONFLICT
            self._conflict = "Hotkey already in use by another application"
            logger.warning("RegisterHotKey failed: %s", exc)
            self._schedule_status()
            win32gui.DestroyWindow(hwnd)
            return

        if not ok:
            self._status = HotkeyServiceStatus.CONFLICT
            self._conflict = "Hotkey already in use by another application"
            self._schedule_status()
            win32gui.DestroyWindow(hwnd)
            return

        self._registered = True
        self._status = HotkeyServiceStatus.REGISTERED
        self._conflict = None
        self._schedule_status()
        logger.info("Global hotkey registered (%s)", combo)

        try:
            while not self._stop.is_set():
                # PeekMessage with timeout-ish via short wait
                if win32gui.PumpWaitingMessages() == 0:
                    self._stop.wait(0.05)
        finally:
            try:
                win32gui.UnregisterHotKey(hwnd, HOTKEY_ID)
            except Exception:
                pass
            try:
                win32gui.DestroyWindow(hwnd)
            except Exception:
                pass
            self._registered = False

    def _wnd_proc(self, hwnd, msg, wparam, lparam):  # noqa: ANN001
        import win32con

        if msg == win32con.WM_HOTKEY and wparam == HOTKEY_ID:
            self._last_triggered = datetime.now(timezone.utc)
            if self._on_show:
                try:
                    self._on_show()
                except Exception:
                    logger.exception("Show-dashboard handler failed")
            self._schedule_triggered()
            return 0
        import win32gui

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _schedule_status(self) -> None:
        if self._loop and self._bus:
            status = self.get_status().model_dump(mode="json")
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._bus.publish(HOTKEY_STATUS_CHANGED, status))  # type: ignore[union-attr]
            )

    def _schedule_triggered(self) -> None:
        if self._loop and self._bus:
            payload = {"action": HotkeyAction.SHOW_DASHBOARD.value}
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._bus.publish(HOTKEY_TRIGGERED, payload))  # type: ignore[union-attr]
            )

    async def _publish_status(self) -> None:
        if self._bus is None:
            return
        await self._bus.publish(HOTKEY_STATUS_CHANGED, self.get_status().model_dump(mode="json"))
