"""Focus / restore approved windows via opaque IDs."""

from __future__ import annotations

import logging

from app.models.window import FocusResultCode, WindowFocusResult
from app.services.windows.opaque_ids import OpaqueWindowIdStore
from app.services.windows.window_classifier import InventoryWin32Api
from app.services.workspace.window_manager import SW_RESTORE

logger = logging.getLogger(__name__)


class WindowSwitcher:
    def __init__(
        self,
        *,
        api: InventoryWin32Api | None,
        store: OpaqueWindowIdStore,
    ) -> None:
        self._api = api
        self._store = store

    def focus(self, window_id: str, *, expected_app: str | None = None) -> WindowFocusResult:
        binding = self._store.get(window_id)
        if binding is None:
            return WindowFocusResult(
                application_id=expected_app or "",
                window_id=window_id,
                result=FocusResultCode.WINDOW_NOT_FOUND,
                error="Window no longer available",
            )
        if expected_app and binding.application_id != expected_app:
            return WindowFocusResult(
                application_id=binding.application_id,
                window_id=window_id,
                result=FocusResultCode.ACCESS_LIMITED,
                error="Window application mismatch",
            )
        if self._api is None:
            return WindowFocusResult(
                application_id=binding.application_id,
                window_id=window_id,
                result=FocusResultCode.ACCESS_LIMITED,
                error="Window API unavailable",
            )
        try:
            if not self._api.is_window(binding.hwnd):
                return WindowFocusResult(
                    application_id=binding.application_id,
                    window_id=window_id,
                    result=FocusResultCode.WINDOW_NOT_FOUND,
                    error="Window handle invalid",
                )
            restored = False
            if self._api.is_iconic(binding.hwnd):
                restored = bool(self._api.show_window(binding.hwnd, SW_RESTORE))
            focused = bool(self._api.set_foreground_window(binding.hwnd))
            self._store.mark_focused(window_id)
            if focused:
                return WindowFocusResult(
                    application_id=binding.application_id,
                    window_id=window_id,
                    result=FocusResultCode.FOCUSED if not restored else FocusResultCode.RESTORED,
                    restored=restored,
                    foreground=True,
                )
            return WindowFocusResult(
                application_id=binding.application_id,
                window_id=window_id,
                result=FocusResultCode.RUNNING_FOCUS_LIMITED,
                restored=restored,
                foreground=False,
                focus_limited=True,
                error="Windows denied foreground focus",
            )
        except Exception as exc:
            logger.debug("Window focus failed: %s", exc, exc_info=True)
            return WindowFocusResult(
                application_id=binding.application_id,
                window_id=window_id,
                result=FocusResultCode.FAILED,
                error="Focus failed",
            )

    def restore(self, window_id: str) -> WindowFocusResult:
        binding = self._store.get(window_id)
        if binding is None or self._api is None:
            return WindowFocusResult(
                application_id="",
                window_id=window_id,
                result=FocusResultCode.WINDOW_NOT_FOUND,
                error="Window no longer available",
            )
        try:
            if not self._api.is_window(binding.hwnd):
                return WindowFocusResult(
                    application_id=binding.application_id,
                    window_id=window_id,
                    result=FocusResultCode.WINDOW_NOT_FOUND,
                )
            restored = False
            if self._api.is_iconic(binding.hwnd):
                restored = bool(self._api.show_window(binding.hwnd, SW_RESTORE))
            return WindowFocusResult(
                application_id=binding.application_id,
                window_id=window_id,
                result=FocusResultCode.RESTORED if restored else FocusResultCode.FOCUSED,
                restored=restored,
            )
        except Exception:
            return WindowFocusResult(
                application_id=binding.application_id,
                window_id=window_id,
                result=FocusResultCode.FAILED,
                error="Restore failed",
            )
