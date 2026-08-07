"""Approved browser destination registry and URL validation."""

from __future__ import annotations

from urllib.parse import urlparse

from app.models.browser import BrowserDestinationDefinition


DEFAULT_DESTINATIONS: list[BrowserDestinationDefinition] = [
    BrowserDestinationDefinition(
        id="dashboard",
        display_name="Jarvis Dashboard",
        url="http://localhost:5173/",
        allowed_hosts=["localhost", "127.0.0.1"],
    ),
    BrowserDestinationDefinition(
        id="gmail",
        display_name="Gmail",
        url="https://mail.google.com/",
        allowed_hosts=["mail.google.com"],
    ),
    BrowserDestinationDefinition(
        id="news",
        display_name="News",
        url="https://news.google.com/",
        allowed_hosts=["news.google.com"],
    ),
]


class BrowserDestinationRegistry:
    def __init__(
        self,
        destinations: list[BrowserDestinationDefinition] | None = None,
        *,
        dashboard_url: str | None = None,
        gmail_url: str | None = None,
        news_url: str | None = None,
    ) -> None:
        items = list(destinations or DEFAULT_DESTINATIONS)
        by_id = {item.id: item for item in items}
        if dashboard_url:
            by_id["dashboard"] = BrowserDestinationDefinition(
                id="dashboard",
                display_name="Jarvis Dashboard",
                url=dashboard_url,
                allowed_hosts=["localhost", "127.0.0.1"],
            )
        if gmail_url:
            host = urlparse(gmail_url).hostname or "mail.google.com"
            by_id["gmail"] = BrowserDestinationDefinition(
                id="gmail",
                display_name="Gmail",
                url=gmail_url,
                allowed_hosts=[host],
            )
        if news_url:
            host = urlparse(news_url).hostname or "news.google.com"
            by_id["news"] = BrowserDestinationDefinition(
                id="news",
                display_name="News",
                url=news_url,
                allowed_hosts=[host],
            )
        self._by_id = by_id

    def list(self) -> list[BrowserDestinationDefinition]:
        return list(self._by_id.values())

    def get(self, destination_id: str) -> BrowserDestinationDefinition | None:
        return self._by_id.get(destination_id)

    def matches(self, destination_id: str, url: str) -> bool:
        dest = self.get(destination_id)
        if dest is None:
            return False
        return url_matches_destination(url, dest)


def url_matches_destination(url: str, dest: BrowserDestinationDefinition) -> bool:
    """Strict host/scheme matching — no substring tricks."""
    try:
        parsed = urlparse(url)
        expected = urlparse(dest.url)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.scheme != expected.scheme and not (
        dest.id == "dashboard" and parsed.scheme in {"http", "https"}
    ):
        if dest.id != "dashboard":
            return False
    host = (parsed.hostname or "").lower()
    if host not in {h.lower() for h in dest.allowed_hosts}:
        return False
    # Path: require destination path prefix when non-root
    expected_path = expected.path or "/"
    actual_path = parsed.path or "/"
    if expected_path != "/" and not actual_path.startswith(expected_path.rstrip("/") ):
        # allow exact prefix match
        if not actual_path.startswith(expected_path):
            return False
    return True
