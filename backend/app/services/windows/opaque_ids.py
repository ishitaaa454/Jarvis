"""Opaque temporary window IDs — HWND stays backend-only."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class WindowBinding:
    window_id: str
    hwnd: int
    application_id: str
    process_id: int
    first_seen_at: datetime
    last_seen_at: datetime
    last_jarvis_focus_at: datetime | None = None
    raw_title: str = ""


class OpaqueWindowIdStore:
    """Maps opaque IDs ↔ HWND. Regenerated after backend restart."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._by_id: dict[str, WindowBinding] = {}
        self._by_hwnd: dict[int, str] = {}

    def upsert(
        self,
        *,
        hwnd: int,
        application_id: str,
        process_id: int,
        raw_title: str = "",
    ) -> WindowBinding:
        now = datetime.now(timezone.utc)
        with self._lock:
            existing_id = self._by_hwnd.get(hwnd)
            if existing_id and existing_id in self._by_id:
                binding = self._by_id[existing_id]
                binding.last_seen_at = now
                binding.process_id = process_id
                binding.application_id = application_id
                binding.raw_title = raw_title
                return binding

            window_id = f"win_{secrets.token_hex(8)}"
            binding = WindowBinding(
                window_id=window_id,
                hwnd=hwnd,
                application_id=application_id,
                process_id=process_id,
                first_seen_at=now,
                last_seen_at=now,
                raw_title=raw_title,
            )
            self._by_id[window_id] = binding
            self._by_hwnd[hwnd] = window_id
            return binding

    def get(self, window_id: str) -> WindowBinding | None:
        with self._lock:
            return self._by_id.get(window_id)

    def mark_focused(self, window_id: str) -> None:
        with self._lock:
            binding = self._by_id.get(window_id)
            if binding:
                binding.last_jarvis_focus_at = datetime.now(timezone.utc)

    def prune_missing(self, live_hwnds: set[int]) -> list[str]:
        """Remove bindings whose HWND disappeared. Returns removed window IDs."""
        removed: list[str] = []
        with self._lock:
            stale_hwnds = [hwnd for hwnd in self._by_hwnd if hwnd not in live_hwnds]
            for hwnd in stale_hwnds:
                wid = self._by_hwnd.pop(hwnd, None)
                if wid and wid in self._by_id:
                    del self._by_id[wid]
                    removed.append(wid)
        return removed

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._by_hwnd.clear()
