"""pywin32-backed window discovery, restore, and best-effort focus.

Uses a Protocol so tests can inject a fake Win32 API without pywin32
installed. If pywin32 is unavailable at runtime, the manager degrades
gracefully (``available`` is False, all operations become no-ops) instead
of crashing the workspace launch.

Window titles are never logged unless ``debug_titles`` is explicitly
enabled (WORKSPACE_DEBUG_WINDOW_DISCOVERY), and are omitted from returned
``WindowInfo`` objects by default.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)

SW_RESTORE = 9


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    pid: int
    title: str = ""


class Win32WindowApi(Protocol):
    """Minimal surface needed from pywin32's win32gui/win32process."""

    def enum_windows(self) -> list[int]: ...

    def get_window_text(self, hwnd: int) -> str: ...

    def is_window_visible(self, hwnd: int) -> bool: ...

    def is_iconic(self, hwnd: int) -> bool: ...

    def get_pid_for_window(self, hwnd: int) -> int: ...

    def show_window(self, hwnd: int, cmd: int) -> bool: ...

    def set_foreground_window(self, hwnd: int) -> bool: ...


class Pywin32WindowApi:
    """Thin adapter over win32gui/win32process. Import is lazy and optional."""

    def __init__(self) -> None:
        import win32gui  # noqa: F401 — presence check
        import win32process  # noqa: F401 — presence check

        self._gui = win32gui
        self._process = win32process

    def enum_windows(self) -> list[int]:
        handles: list[int] = []
        self._gui.EnumWindows(lambda hwnd, _: handles.append(hwnd), None)
        return handles

    def get_window_text(self, hwnd: int) -> str:
        try:
            return str(self._gui.GetWindowText(hwnd))
        except Exception:
            return ""

    def is_window_visible(self, hwnd: int) -> bool:
        try:
            return bool(self._gui.IsWindowVisible(hwnd))
        except Exception:
            return False

    def is_iconic(self, hwnd: int) -> bool:
        try:
            return bool(self._gui.IsIconic(hwnd))
        except Exception:
            return False

    def get_pid_for_window(self, hwnd: int) -> int:
        try:
            _, pid = self._process.GetWindowThreadProcessId(hwnd)
            return int(pid)
        except Exception:
            return 0

    def show_window(self, hwnd: int, cmd: int) -> bool:
        try:
            self._gui.ShowWindow(hwnd, cmd)
            return True
        except Exception:
            return False

    def set_foreground_window(self, hwnd: int) -> bool:
        try:
            self._gui.SetForegroundWindow(hwnd)
            return True
        except Exception:
            # Windows may deny foreground focus changes; this is best-effort.
            return False


def try_create_default_api() -> Win32WindowApi | None:
    try:
        return Pywin32WindowApi()
    except Exception:
        logger.warning("pywin32 is not available; window discovery/focus disabled")
        return None


class WindowManager:
    def __init__(
        self,
        *,
        api: Win32WindowApi | None = None,
        debug_titles: bool = False,
    ) -> None:
        self._api = api if api is not None else try_create_default_api()
        self._debug_titles = debug_titles

    @property
    def available(self) -> bool:
        return self._api is not None

    def find_windows_for_pids(
        self,
        pids: list[int],
        title_patterns: list[str] | None = None,
    ) -> list[WindowInfo]:
        if self._api is None or not pids:
            return []

        pid_set = set(pids)
        patterns = [p.lower() for p in (title_patterns or []) if p]

        try:
            handles = self._api.enum_windows()
        except Exception:
            logger.exception("Window enumeration failed")
            return []

        results: list[WindowInfo] = []
        for hwnd in handles:
            try:
                if not self._api.is_window_visible(hwnd):
                    continue
                pid = self._api.get_pid_for_window(hwnd)
                if pid not in pid_set:
                    continue
                title = self._api.get_window_text(hwnd)
                if not title:
                    continue
                if patterns and not any(pattern in title.lower() for pattern in patterns):
                    continue
                results.append(
                    WindowInfo(hwnd=hwnd, pid=pid, title=title if self._debug_titles else "")
                )
            except Exception:
                continue

        if self._debug_titles and results:
            logger.debug("Discovered %d matching window(s)", len(results))
        return results

    def restore(self, window: WindowInfo) -> bool:
        if self._api is None:
            return False
        try:
            if self._api.is_iconic(window.hwnd):
                return self._api.show_window(window.hwnd, SW_RESTORE)
            return True
        except Exception:
            logger.exception("Failed to restore window")
            return False

    def focus(self, window: WindowInfo) -> bool:
        """Best-effort foreground focus. Windows may deny this; not a failure."""
        if self._api is None:
            return False
        try:
            return self._api.set_foreground_window(window.hwnd)
        except Exception:
            logger.debug("SetForegroundWindow denied (best-effort)", exc_info=True)
            return False
