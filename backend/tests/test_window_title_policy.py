"""Phase 7 window title policy and opaque ID tests."""

from __future__ import annotations

from app.models.window import WindowTitleMode
from app.services.windows.opaque_ids import OpaqueWindowIdStore
from app.services.windows.recent_window_tracker import RecentWindowTracker
from app.services.windows.window_title_policy import sanitize_window_title


def test_vscode_safe_title() -> None:
    title = sanitize_window_title(
        application_id="vscode",
        raw_title="jarvis-workspace - Visual Studio Code",
        display_name="Visual Studio Code",
        mode=WindowTitleMode.SAFE,
    )
    assert title == "jarvis-workspace"


def test_gmail_title_protected() -> None:
    title = sanitize_window_title(
        application_id="gmail",
        raw_title="Inbox (7) - secret@example.com - Gmail",
        display_name="Gmail",
        mode=WindowTitleMode.SAFE,
    )
    assert title == "Gmail"
    assert "secret" not in title


def test_teams_whatsapp_spotify_protected() -> None:
    for app_id, expected in [
        ("teams", "Microsoft Teams"),
        ("whatsapp", "WhatsApp"),
        ("spotify", "Spotify"),
    ]:
        title = sanitize_window_title(
            application_id=app_id,
            raw_title="Private Chat — Alice",
            display_name=expected,
            mode=WindowTitleMode.SAFE,
        )
        assert title == expected


def test_chrome_generic_safe_title() -> None:
    title = sanitize_window_title(
        application_id="chrome",
        raw_title="Some Private Page - Google Chrome",
        display_name="Google Chrome",
        mode=WindowTitleMode.SAFE,
    )
    assert title == "Chrome window"


def test_hidden_mode() -> None:
    title = sanitize_window_title(
        application_id="vscode",
        raw_title="secret.md - Visual Studio Code",
        display_name="Visual Studio Code",
        mode=WindowTitleMode.HIDDEN,
    )
    assert title == "Visual Studio Code"


def test_full_mode_requires_allow_flag() -> None:
    raw = "secret.md - Visual Studio Code"
    denied = sanitize_window_title(
        application_id="vscode",
        raw_title=raw,
        display_name="Visual Studio Code",
        mode=WindowTitleMode.FULL,
        allow_full=False,
    )
    assert denied == "secret.md"
    allowed = sanitize_window_title(
        application_id="vscode",
        raw_title=raw,
        display_name="Visual Studio Code",
        mode=WindowTitleMode.FULL,
        allow_full=True,
    )
    assert allowed == raw


def test_opaque_ids_never_expose_hwnd_in_id() -> None:
    store = OpaqueWindowIdStore()
    binding = store.upsert(hwnd=12345, application_id="vscode", process_id=99, raw_title="x")
    assert "12345" not in binding.window_id
    assert binding.window_id.startswith("win_")
    assert store.get(binding.window_id) is binding


def test_recent_windows_bounded_and_safe() -> None:
    tracker = RecentWindowTracker(limit=3)
    for i in range(5):
        tracker.record(
            window_id=f"win_{i}",
            application_id="vscode",
            display_name="Visual Studio Code",
            display_title="file",
        )
    items = tracker.list()
    assert len(items) == 3
    assert items[0].window_id == "win_4"
