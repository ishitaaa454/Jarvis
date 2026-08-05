"""BrowserController URL validation, dedupe, and launch tests — no real Chrome."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.workspace.browser_controller import BrowserController, is_url_allowed
from app.services.workspace.process_manager import ProcessManager


class FakeLauncher:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, list[str]]] = []
        self.raise_error: Exception | None = None

    def launch_executable(self, path: Path, args: list[str]) -> int:
        if self.raise_error:
            raise self.raise_error
        self.calls.append((path, args))
        return 999


class FakeProcessManager:
    def __init__(self, running: bool = False) -> None:
        self._running = running

    def is_running(self, names: list[str]) -> bool:
        return self._running


@pytest.mark.parametrize(
    "url,allow_localhost,expected",
    [
        ("https://mail.google.com/", False, True),
        ("http://mail.google.com/", False, False),
        ("javascript:alert(1)", False, False),
        ("data:text/html,<script>", False, False),
        ("file:///etc/passwd", False, False),
        ("http://localhost:5173", True, True),
        ("http://127.0.0.1:8000", True, True),
        ("http://localhost:5173", False, False),
        ("http://evil.com", True, False),
        ("", False, False),
    ],
)
def test_is_url_allowed(url: str, allow_localhost: bool, expected: bool) -> None:
    assert is_url_allowed(url, allow_localhost_http=allow_localhost) is expected


def _make_controller(*, allow_localhost=False, launcher=None, chrome_path="C:/chrome.exe"):
    launcher = launcher or FakeLauncher()
    resolved = Path(chrome_path) if chrome_path else None
    return BrowserController(
        resolve_chrome=lambda: resolved,
        process_manager=FakeProcessManager(),
        launcher=launcher,
        allow_localhost_http=allow_localhost,
    ), launcher


def test_open_url_success() -> None:
    controller, launcher = _make_controller()
    ok, error = controller.open_url("https://mail.google.com/")
    assert ok is True
    assert error is None
    assert launcher.calls == [(Path("C:/chrome.exe"), ["https://mail.google.com/"])]


def test_open_url_rejects_javascript_scheme() -> None:
    controller, launcher = _make_controller()
    ok, error = controller.open_url("javascript:alert(1)")
    assert ok is False
    assert error is not None
    assert launcher.calls == []


def test_open_url_dedupes_within_session() -> None:
    controller, launcher = _make_controller()
    controller.open_url("https://mail.google.com/")
    controller.open_url("https://mail.google.com/")
    assert len(launcher.calls) == 1


def test_reset_session_clears_dedupe() -> None:
    controller, launcher = _make_controller()
    controller.open_url("https://mail.google.com/")
    controller.reset_session()
    controller.open_url("https://mail.google.com/")
    assert len(launcher.calls) == 2


def test_open_url_fails_when_chrome_unresolved() -> None:
    controller, launcher = _make_controller(chrome_path=None)
    ok, error = controller.open_url("https://mail.google.com/")
    assert ok is False
    assert "Chrome" in (error or "")


def test_open_url_handles_launch_exception() -> None:
    launcher = FakeLauncher()
    launcher.raise_error = RuntimeError("boom")
    controller, _ = _make_controller(launcher=launcher)
    ok, error = controller.open_url("https://mail.google.com/")
    assert ok is False
    assert error == "Failed to launch browser"


def test_is_chrome_running_delegates_to_process_manager() -> None:
    controller = BrowserController(
        resolve_chrome=lambda: Path("C:/chrome.exe"),
        process_manager=FakeProcessManager(running=True),
        launcher=FakeLauncher(),
    )
    assert controller.is_chrome_running() is True
