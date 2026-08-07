"""Phase 7 hotkey + preview policy tests (no real RegisterHotKey)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app
from app.models.hotkey import HotkeyServiceStatus
from app.models.window import PreviewAvailability
from app.services.hotkeys.global_hotkey_service import ALLOWED_HOTKEYS, GlobalHotkeyService
from app.services.windows.opaque_ids import OpaqueWindowIdStore
from app.services.windows.window_preview_provider import WindowPreviewProvider


def test_allowed_hotkeys_are_modifier_safe() -> None:
    assert "CTRL+ALT+J" in ALLOWED_HOTKEYS
    assert "CTRL+SHIFT+J" in ALLOWED_HOTKEYS


def test_hotkey_settings_reject_unsafe_combo() -> None:
    with pytest.raises(Exception):
        Settings(global_hotkey_show_dashboard="ALT+F4")


@pytest.mark.asyncio
async def test_hotkey_disabled_state() -> None:
    service = GlobalHotkeyService(Settings(global_hotkey_enabled=False))
    await service.start()
    status = service.get_status()
    assert status.status == HotkeyServiceStatus.DISABLED
    await service.stop()


def test_preview_disabled_and_sensitive_blocked() -> None:
    store = OpaqueWindowIdStore()
    binding = store.upsert(hwnd=1, application_id="gmail", process_id=1)
    provider = WindowPreviewProvider(
        Settings(window_previews_enabled=False, allow_sensitive_app_previews=False),
        store=store,
        app_preview_flags={"gmail": True},
    )
    assert provider.availability(binding.window_id) == PreviewAvailability.DISABLED

    provider2 = WindowPreviewProvider(
        Settings(window_previews_enabled=True, allow_sensitive_app_previews=False),
        store=store,
        app_preview_flags={"gmail": True},
    )
    assert provider2.availability(binding.window_id) == PreviewAvailability.BLOCKED


def test_windows_api_no_hwnd_and_preview_forbidden() -> None:
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.get("/api/windows")
    assert response.status_code == 200
    body = response.json()
    dumped = str(body)
    assert "hwnd" not in dumped.lower()

    preview = client.get("/api/windows/win_missing/preview")
    assert preview.status_code in {403, 404}

    hotkeys = client.get("/api/hotkeys/status")
    assert hotkeys.status_code == 200
    assert "shortcuts" in hotkeys.json()

    browser = client.get("/api/browser/destinations")
    assert browser.status_code == 200
    ids = {d["id"] for d in browser.json()["destinations"]}
    assert {"dashboard", "gmail", "news"} <= ids
