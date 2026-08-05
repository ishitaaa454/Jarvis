"""WindowManager tests using a fake Win32 API — never touches real windows."""

from __future__ import annotations

from app.services.workspace.window_manager import SW_RESTORE, WindowManager


class FakeWin32Api:
    def __init__(self) -> None:
        self.handles = [1001, 1002, 1003]
        self.titles = {1001: "Visual Studio Code", 1002: "Untitled - Notepad", 1003: ""}
        self.visible = {1001: True, 1002: True, 1003: True}
        self.pids = {1001: 111, 1002: 222, 1003: 111}
        self.iconic = {1001: False, 1002: False, 1003: False}
        self.show_window_calls: list[tuple[int, int]] = []
        self.foreground_calls: list[int] = []
        self.deny_foreground = False

    def enum_windows(self) -> list[int]:
        return list(self.handles)

    def get_window_text(self, hwnd: int) -> str:
        return self.titles.get(hwnd, "")

    def is_window_visible(self, hwnd: int) -> bool:
        return self.visible.get(hwnd, False)

    def is_iconic(self, hwnd: int) -> bool:
        return self.iconic.get(hwnd, False)

    def get_pid_for_window(self, hwnd: int) -> int:
        return self.pids.get(hwnd, 0)

    def show_window(self, hwnd: int, cmd: int) -> bool:
        self.show_window_calls.append((hwnd, cmd))
        return True

    def set_foreground_window(self, hwnd: int) -> bool:
        self.foreground_calls.append(hwnd)
        if self.deny_foreground:
            return False
        return True


def test_find_windows_for_pids_matches_by_pid() -> None:
    api = FakeWin32Api()
    manager = WindowManager(api=api)
    results = manager.find_windows_for_pids([111])
    assert len(results) == 1
    assert results[0].hwnd == 1001


def test_find_windows_filters_by_title_pattern() -> None:
    api = FakeWin32Api()
    manager = WindowManager(api=api)
    results = manager.find_windows_for_pids([111, 222], title_patterns=["notepad"])
    assert len(results) == 1
    assert results[0].hwnd == 1002


def test_find_windows_skips_empty_titles() -> None:
    api = FakeWin32Api()
    manager = WindowManager(api=api)
    results = manager.find_windows_for_pids([111])
    hwnds = {w.hwnd for w in results}
    assert 1003 not in hwnds  # empty title window, same pid as 1001


def test_find_windows_returns_empty_when_no_pids() -> None:
    api = FakeWin32Api()
    manager = WindowManager(api=api)
    assert manager.find_windows_for_pids([]) == []


def test_titles_hidden_by_default() -> None:
    api = FakeWin32Api()
    manager = WindowManager(api=api)
    results = manager.find_windows_for_pids([111])
    assert results[0].title == ""


def test_titles_included_when_debug_enabled() -> None:
    api = FakeWin32Api()
    manager = WindowManager(api=api, debug_titles=True)
    results = manager.find_windows_for_pids([111])
    assert results[0].title == "Visual Studio Code"


def test_restore_calls_show_window_when_iconic() -> None:
    api = FakeWin32Api()
    api.iconic[1001] = True
    manager = WindowManager(api=api)
    window = manager.find_windows_for_pids([111])[0]
    assert manager.restore(window) is True
    assert api.show_window_calls == [(1001, SW_RESTORE)]


def test_restore_skips_show_window_when_not_iconic() -> None:
    api = FakeWin32Api()
    manager = WindowManager(api=api)
    window = manager.find_windows_for_pids([111])[0]
    assert manager.restore(window) is True
    assert api.show_window_calls == []


def test_focus_best_effort_success() -> None:
    api = FakeWin32Api()
    manager = WindowManager(api=api)
    window = manager.find_windows_for_pids([111])[0]
    assert manager.focus(window) is True


def test_focus_denial_does_not_raise() -> None:
    api = FakeWin32Api()
    api.deny_foreground = True
    manager = WindowManager(api=api)
    window = manager.find_windows_for_pids([111])[0]
    assert manager.focus(window) is False


def test_graceful_when_win32_unavailable(monkeypatch) -> None:
    import app.services.workspace.window_manager as window_manager_module

    monkeypatch.setattr(window_manager_module, "try_create_default_api", lambda: None)
    manager = window_manager_module.WindowManager()

    assert manager.available is False
    assert manager.find_windows_for_pids([111]) == []

    from app.services.workspace.window_manager import WindowInfo

    fake_window = WindowInfo(hwnd=1, pid=1, title="")
    assert manager.restore(fake_window) is False
    assert manager.focus(fake_window) is False


def test_enum_windows_exception_returns_empty() -> None:
    class BrokenApi(FakeWin32Api):
        def enum_windows(self) -> list[int]:
            raise RuntimeError("boom")

    manager = WindowManager(api=BrokenApi())
    assert manager.find_windows_for_pids([111]) == []


def test_try_create_default_api_returns_none_without_pywin32(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in {"win32gui", "win32process"}:
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from app.services.workspace.window_manager import try_create_default_api

    assert try_create_default_api() is None
