"""Optional in-memory window preview capture (disabled by default)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.models.preview import PreviewResult
from app.models.window import PreviewAvailability
from app.services.windows.opaque_ids import OpaqueWindowIdStore
from app.services.windows.window_classifier import InventoryWin32Api

logger = logging.getLogger(__name__)

SENSITIVE_APPS = frozenset({"gmail", "teams", "whatsapp"})


class WindowPreviewProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        store: OpaqueWindowIdStore,
        api: InventoryWin32Api | None = None,
        app_preview_flags: dict[str, bool] | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._api = api
        self._flags = app_preview_flags or {}
        self._cache: dict[str, tuple[float, bytes, PreviewResult]] = {}

    def set_api(self, api: InventoryWin32Api | None) -> None:
        self._api = api

    def set_flags(self, flags: dict[str, bool]) -> None:
        self._flags = flags

    def availability(self, window_id: str) -> PreviewAvailability:
        if not self._settings.window_previews_enabled:
            return PreviewAvailability.DISABLED
        binding = self._store.get(window_id)
        if binding is None:
            return PreviewAvailability.WINDOW_NOT_FOUND
        if binding.application_id in SENSITIVE_APPS and not self._settings.allow_sensitive_app_previews:
            return PreviewAvailability.BLOCKED
        if not self._flags.get(binding.application_id, False):
            return PreviewAvailability.BLOCKED
        return PreviewAvailability.AVAILABLE

    def capture(self, window_id: str) -> tuple[PreviewAvailability, bytes | None, PreviewResult]:
        status = self.availability(window_id)
        meta = PreviewResult(window_id=window_id, available=False, reason=status.value)
        if status != PreviewAvailability.AVAILABLE:
            return status, None, meta
        binding = self._store.get(window_id)
        if binding is None or self._api is None:
            return PreviewAvailability.UNAVAILABLE, None, meta

        import time

        now = time.monotonic()
        cached = self._cache.get(window_id)
        if cached and now - cached[0] < self._settings.window_preview_cache_seconds:
            return PreviewAvailability.AVAILABLE, cached[1], cached[2]

        # PrintWindow path is best-effort; never fall back to desktop capture.
        try:
            data = self._print_window(binding.hwnd)
        except Exception:
            logger.debug("Preview capture failed", exc_info=True)
            data = None
        if not data:
            meta.reason = "PREVIEW_UNAVAILABLE"
            return PreviewAvailability.UNAVAILABLE, None, meta

        result = PreviewResult(
            window_id=window_id,
            available=True,
            content_type="image/jpeg",
            captured_at=datetime.now(timezone.utc),
        )
        self._cache[window_id] = (now, data, result)
        # Bound cache size
        if len(self._cache) > 8:
            oldest = sorted(self._cache.items(), key=lambda item: item[1][0])[0][0]
            self._cache.pop(oldest, None)
        return PreviewAvailability.AVAILABLE, data, result

    def _print_window(self, hwnd: int) -> bytes | None:
        """Capture via PrintWindow + Pillow when available. Returns JPEG bytes."""
        try:
            import win32gui
            import win32ui
            from PIL import Image
        except Exception:
            return None

        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = max(1, right - left)
            height = max(1, bottom - top)
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)
            # 0 = whole window
            result = win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
            if not result:
                return None
            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)
            image = Image.frombuffer(
                "RGB",
                (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                bmpstr,
                "raw",
                "BGRX",
                0,
                1,
            )
            max_w = self._settings.window_preview_max_width
            if image.width > max_w:
                ratio = max_w / float(image.width)
                image = image.resize((max_w, max(1, int(image.height * ratio))))
            mode = (self._settings.window_preview_mode or "OFF").upper()
            if mode == "BLURRED":
                image = image.filter(__import__("PIL.ImageFilter", fromlist=["ImageFilter"]).ImageFilter.GaussianBlur(radius=8))
            import io

            buf = io.BytesIO()
            quality = int(self._settings.window_preview_jpeg_quality)
            image.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            # Cleanup GDI
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            if len(data) < 64:
                return None
            return data
        except Exception:
            logger.debug("PrintWindow capture error", exc_info=True)
            return None
