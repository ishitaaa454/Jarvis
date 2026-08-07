"""Optional Chrome DevTools Protocol provider (loopback-only, filtered)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.services.browser.browser_destination_registry import (
    BrowserDestinationRegistry,
    url_matches_destination,
)

logger = logging.getLogger(__name__)


@dataclass
class CdpTab:
    tab_id: str
    url: str
    title: str


class ChromeCdpProvider:
    """Talks to local Chrome /json endpoints only. Never requests cookies or JS."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 9222,
        timeout_seconds: float = 2.0,
        registry: BrowserDestinationRegistry | None = None,
        enabled: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout_seconds
        self._registry = registry or BrowserDestinationRegistry()
        self._enabled = enabled

    def validate_host(self) -> bool:
        return self._host in {"127.0.0.1", "localhost", "::1"}

    def available(self) -> bool:
        if not self._enabled or not self.validate_host():
            return False
        try:
            self._get_json("/json/version")
            return True
        except Exception:
            return False

    def list_approved_tabs(self) -> list[tuple[str, CdpTab]]:
        """Return only tabs matching approved destinations: (destination_id, tab)."""
        if not self._enabled or not self.validate_host():
            return []
        try:
            tabs = self._get_json("/json")
        except Exception:
            return []
        if not isinstance(tabs, list):
            return []
        matched: list[tuple[str, CdpTab]] = []
        for entry in tabs:
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("url") or "")
            tab_id = str(entry.get("id") or "")
            title = str(entry.get("title") or "")
            if not tab_id or not url:
                continue
            for dest in self._registry.list():
                if url_matches_destination(url, dest):
                    matched.append(
                        (
                            dest.id,
                            CdpTab(tab_id=tab_id, url=url, title=title),
                        )
                    )
                    break
        return matched

    def activate_tab(self, tab_id: str) -> bool:
        if not self._enabled or not self.validate_host():
            return False
        # Only activate IDs we previously listed as approved
        approved_ids = {tab.tab_id for _, tab in self.list_approved_tabs()}
        if tab_id not in approved_ids:
            return False
        try:
            self._get_json(f"/json/activate/{tab_id}")
            return True
        except Exception:
            logger.debug("CDP activate failed", exc_info=True)
            return False

    def find_destination_tab(self, destination_id: str) -> CdpTab | None:
        for dest_id, tab in self.list_approved_tabs():
            if dest_id == destination_id:
                return tab
        return None

    def _get_json(self, path: str) -> Any:
        url = f"http://{self._host}:{self._port}{path}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
            body = resp.read().decode("utf-8")
            if not body:
                return {}
            return json.loads(body)
