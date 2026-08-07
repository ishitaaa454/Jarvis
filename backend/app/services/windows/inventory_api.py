"""pywin32 inventory API extending the Phase 4 window surface."""

from __future__ import annotations

import logging

from app.services.windows.window_classifier import InventoryWin32Api
from app.services.workspace.window_manager import Pywin32WindowApi, try_create_default_api

logger = logging.getLogger(__name__)


class Pywin32InventoryApi(Pywin32WindowApi):
    def get_foreground_window(self) -> int:
        try:
            return int(self._gui.GetForegroundWindow())
        except Exception:
            return 0

    def get_class_name(self, hwnd: int) -> str:
        try:
            return str(self._gui.GetClassName(hwnd))
        except Exception:
            return ""

    def get_window_rect(self, hwnd: int) -> tuple[int, int, int, int]:
        try:
            return tuple(self._gui.GetWindowRect(hwnd))  # type: ignore[return-value]
        except Exception:
            return (0, 0, 0, 0)

    def is_window(self, hwnd: int) -> bool:
        try:
            return bool(self._gui.IsWindow(hwnd))
        except Exception:
            return False


def try_create_inventory_api() -> InventoryWin32Api | None:
    try:
        return Pywin32InventoryApi()
    except Exception:
        # Fall back: wrap base API if present (tests inject fakes).
        base = try_create_default_api()
        if base is None:
            logger.warning("pywin32 unavailable; window inventory disabled")
            return None
        return None
