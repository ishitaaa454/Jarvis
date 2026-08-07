"""Phase 7 browser destination + CDP provider tests."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.browser.browser_destination_registry import (
    BrowserDestinationRegistry,
    url_matches_destination,
)
from app.services.browser.browser_integration_service import BrowserIntegrationService
from app.services.browser.chrome_cdp_provider import ChromeCdpProvider, CdpTab
from app.services.browser.session_browser_provider import SessionBrowserProvider


def test_destination_url_validation_rejects_substring_tricks() -> None:
    registry = BrowserDestinationRegistry()
    gmail = registry.get("gmail")
    assert gmail is not None
    assert url_matches_destination("https://mail.google.com/mail/u/0/", gmail)
    assert not url_matches_destination("https://evil.com/?next=mail.google.com", gmail)
    assert not url_matches_destination("https://notmail.google.com/", gmail)


def test_cdp_rejects_non_loopback_via_settings() -> None:
    with pytest.raises(Exception):
        Settings(browser_cdp_host="192.168.1.10")


def test_cdp_filters_unrelated_tabs(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = BrowserDestinationRegistry()
    provider = ChromeCdpProvider(
        host="127.0.0.1",
        port=9222,
        enabled=True,
        registry=registry,
    )

    def fake_get(path: str):
        if path == "/json":
            return [
                {"id": "1", "url": "https://mail.google.com/", "title": "Gmail"},
                {"id": "2", "url": "https://example.com/private", "title": "Secret"},
            ]
        return {}

    monkeypatch.setattr(provider, "_get_json", fake_get)
    matched = provider.list_approved_tabs()
    assert len(matched) == 1
    assert matched[0][0] == "gmail"


@pytest.mark.asyncio
async def test_session_provider_tracks_and_limits_focus() -> None:
    opened: list[str] = []
    settings = Settings(browser_integration_enabled=True, browser_cdp_enabled=False)
    service = BrowserIntegrationService(
        settings,
        chrome_launcher=lambda url: opened.append(url),
    )
    await service.on_startup()
    result = await service.open_destination("gmail")
    assert result.result == "OPENED"
    assert opened and "mail.google.com" in opened[0]
    focus = await service.focus_destination("gmail")
    assert focus.exact_focus is False
    assert focus.result == "FOCUS_LIMITED"


@pytest.mark.asyncio
async def test_unknown_destination_rejected() -> None:
    service = BrowserIntegrationService(Settings())
    result = await service.open_destination("not-a-real-dest")
    assert result.result == "REJECTED"


@pytest.mark.asyncio
async def test_cdp_exact_focus(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(browser_integration_enabled=True, browser_cdp_enabled=True)
    service = BrowserIntegrationService(settings)
    service._status = service.get_status().status

    class FakeCdp:
        def validate_host(self) -> bool:
            return True

        def available(self) -> bool:
            return True

        def list_approved_tabs(self):
            return [("dashboard", CdpTab(tab_id="t1", url="http://localhost:5173/", title="Jarvis"))]

        def find_destination_tab(self, destination_id: str):
            return CdpTab(tab_id="t1", url="http://localhost:5173/", title="Jarvis")

        def activate_tab(self, tab_id: str) -> bool:
            return tab_id == "t1"

    service._cdp = FakeCdp()  # type: ignore[assignment]
    service._status = __import__(
        "app.models.browser", fromlist=["BrowserIntegrationStatus"]
    ).BrowserIntegrationStatus.CONNECTED
    result = await service.focus_destination("dashboard")
    assert result.exact_focus is True
    assert result.result == "FOCUSED"
