"""In-memory recent approved-window tracker."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from app.models.window import RecentWindowRecord


class RecentWindowTracker:
    def __init__(self, *, limit: int = 20) -> None:
        self._limit = max(1, min(int(limit), 50))
        self._items: deque[RecentWindowRecord] = deque(maxlen=self._limit)

    def record(
        self,
        *,
        window_id: str,
        application_id: str,
        display_name: str,
        display_title: str,
        at: datetime | None = None,
    ) -> None:
        stamp = at or datetime.now(timezone.utc)
        # Drop prior entry for same window_id
        remaining = [item for item in self._items if item.window_id != window_id]
        remaining.insert(
            0,
            RecentWindowRecord(
                window_id=window_id,
                application_id=application_id,
                display_name=display_name,
                display_title=display_title,
                last_foreground_at=stamp,
            ),
        )
        self._items = deque(remaining[: self._limit], maxlen=self._limit)

    def list(self) -> list[RecentWindowRecord]:
        return list(self._items)

    def prune(self, valid_ids: set[str]) -> None:
        self._items = deque(
            [item for item in self._items if item.window_id in valid_ids],
            maxlen=self._limit,
        )
