"""Session-scoped tracking of Jarvis-opened browser destinations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SessionDestination:
    destination_id: str
    url: str
    opened_at: datetime
    last_requested_at: datetime
    known_open: bool = True


class SessionBrowserProvider:
    def __init__(self) -> None:
        self._items: dict[str, SessionDestination] = {}

    def mark_opened(self, destination_id: str, url: str) -> SessionDestination:
        now = datetime.now(timezone.utc)
        existing = self._items.get(destination_id)
        if existing:
            existing.last_requested_at = now
            existing.known_open = True
            existing.url = url
            return existing
        item = SessionDestination(
            destination_id=destination_id,
            url=url,
            opened_at=now,
            last_requested_at=now,
        )
        self._items[destination_id] = item
        return item

    def mark_focused(self, destination_id: str) -> SessionDestination | None:
        item = self._items.get(destination_id)
        if item:
            item.last_requested_at = datetime.now(timezone.utc)
            item.known_open = True
        return item

    def get(self, destination_id: str) -> SessionDestination | None:
        return self._items.get(destination_id)

    def list_known(self) -> list[SessionDestination]:
        return list(self._items.values())
