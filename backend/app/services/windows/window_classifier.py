"""Classify top-level windows — keep only useful approved-app surfaces."""

from __future__ import annotations

from typing import Protocol


class InventoryWin32Api(Protocol):
    def enum_windows(self) -> list[int]: ...

    def get_window_text(self, hwnd: int) -> str: ...

    def is_window_visible(self, hwnd: int) -> bool: ...

    def is_iconic(self, hwnd: int) -> bool: ...

    def get_pid_for_window(self, hwnd: int) -> int: ...

    def get_foreground_window(self) -> int: ...

    def get_class_name(self, hwnd: int) -> str: ...

    def get_window_rect(self, hwnd: int) -> tuple[int, int, int, int]: ...

    def is_window(self, hwnd: int) -> bool: ...

    def show_window(self, hwnd: int, cmd: int) -> bool: ...

    def set_foreground_window(self, hwnd: int) -> bool: ...


HELPER_CLASS_PREFIXES = (
    "Chrome_WidgetWin_",  # filtered further by size/title
)
EXCLUDED_CLASS_NAMES = {
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "Progman",
    "WorkerW",
    "NotifyIconOverflowWindow",
    "Windows.UI.Core.CoreWindow",
    "tooltips_class32",
    "#32771",  # alt-tab
    "ForegroundStaging",
}


def is_useful_top_level_window(
    api: InventoryWin32Api,
    hwnd: int,
    *,
    require_title: bool = True,
) -> bool:
    """Return True when the HWND looks like a restorable user window."""
    try:
        if not api.is_window(hwnd):
            return False
        class_name = (api.get_class_name(hwnd) or "").strip()
        if class_name in EXCLUDED_CLASS_NAMES:
            return False
        title = (api.get_window_text(hwnd) or "").strip()
        minimized = api.is_iconic(hwnd)
        visible = api.is_window_visible(hwnd)
        if not visible and not minimized:
            return False
        if require_title and not title and not minimized:
            return False
        try:
            left, top, right, bottom = api.get_window_rect(hwnd)
            width = abs(right - left)
            height = abs(bottom - top)
        except Exception:
            width, height = 1, 1
        if not minimized and (width < 50 or height < 50):
            return False
        # Chromium helper / blank widget surfaces
        if class_name.startswith("Chrome_WidgetWin_") and not title and not minimized:
            return False
        return True
    except Exception:
        return False
