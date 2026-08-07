"""Phase 7 window inventory / switcher tests with fake Win32."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.config import Settings
from app.models.application import ApplicationDefinition, LaunchType
from app.models.window import FocusResultCode
from app.services.windows.opaque_ids import OpaqueWindowIdStore
from app.services.windows.window_classifier import is_useful_top_level_window
from app.services.windows.window_inventory_service import WindowInventoryService
from app.services.windows.window_switcher import WindowSwitcher
from app.services.workspace.process_manager import ProcessInfo


@dataclass
class FakeProc:
    pid: int
    name: str


class FakeProcessManager:
    def __init__(self, mapping: dict[str, list[ProcessInfo]] | None = None) -> None:
        self.mapping = mapping or {}

    def find_by_names(self, names: list[str]) -> list[ProcessInfo]:
        found: list[ProcessInfo] = []
        needles = {n.lower() for n in names}
        for name, procs in self.mapping.items():
            if name.lower() in needles:
                found.extend(procs)
        return found


class FakeInventoryApi:
    def __init__(self) -> None:
        self.windows: dict[int, dict] = {}
        self.foreground = 0
        self.focus_calls: list[int] = []
        self.restore_calls: list[int] = []

    def enum_windows(self) -> list[int]:
        return list(self.windows.keys())

    def get_window_text(self, hwnd: int) -> str:
        return self.windows[hwnd].get("title", "")

    def is_window_visible(self, hwnd: int) -> bool:
        return self.windows[hwnd].get("visible", True)

    def is_iconic(self, hwnd: int) -> bool:
        return self.windows[hwnd].get("minimized", False)

    def get_pid_for_window(self, hwnd: int) -> int:
        return int(self.windows[hwnd].get("pid", 0))

    def get_foreground_window(self) -> int:
        return self.foreground

    def get_class_name(self, hwnd: int) -> str:
        return self.windows[hwnd].get("class", "Chrome_WidgetWin_1")

    def get_window_rect(self, hwnd: int) -> tuple[int, int, int, int]:
        return self.windows[hwnd].get("rect", (0, 0, 800, 600))

    def is_window(self, hwnd: int) -> bool:
        return hwnd in self.windows

    def show_window(self, hwnd: int, cmd: int) -> bool:
        self.restore_calls.append(hwnd)
        self.windows[hwnd]["minimized"] = False
        return True

    def set_foreground_window(self, hwnd: int) -> bool:
        self.focus_calls.append(hwnd)
        denied = self.windows[hwnd].get("deny_focus", False)
        if denied:
            return False
        self.foreground = hwnd
        return True


def _apps() -> list[ApplicationDefinition]:
    return [
        ApplicationDefinition(
            id="vscode",
            display_name="Visual Studio Code",
            launch_type=LaunchType.EXECUTABLE,
            process_names=["Code.exe"],
            window_title_patterns=["Visual Studio Code"],
            favourite=True,
            order=10,
        ),
        ApplicationDefinition(
            id="chrome",
            display_name="Google Chrome",
            launch_type=LaunchType.EXECUTABLE,
            process_names=["chrome.exe"],
            window_title_patterns=["Chrome"],
            favourite=True,
            order=20,
        ),
        ApplicationDefinition(
            id="gmail",
            display_name="Gmail",
            launch_type=LaunchType.BROWSER_URL,
            process_names=["chrome.exe"],
            window_title_patterns=["Gmail"],
            url="https://mail.google.com/",
            order=30,
        ),
    ]


@pytest.mark.asyncio
async def test_inventory_includes_approved_excludes_unapproved() -> None:
    api = FakeInventoryApi()
    api.windows[1] = {
        "title": "jarvis - Visual Studio Code",
        "pid": 100,
        "visible": True,
        "class": "Chrome_WidgetWin_1",
        "rect": (0, 0, 800, 600),
    }
    api.windows[2] = {
        "title": "Notepad",
        "pid": 999,
        "visible": True,
        "class": "Notepad",
        "rect": (0, 0, 400, 300),
    }
    api.foreground = 1
    settings = Settings(window_inventory_enabled=True, window_title_mode="SAFE")
    service = WindowInventoryService(
        settings,
        api=api,
        process_manager=FakeProcessManager(
            {"Code.exe": [ProcessInfo(pid=100, name="Code.exe")]}
        ),
        app_resolver=_apps,
    )
    snap = await service.refresh_now()
    assert snap.available
    vscode = next(a for a in snap.applications if a.application_id == "vscode")
    assert vscode.window_count == 1
    assert vscode.windows[0].display_title == "jarvis"
    assert "hwnd" not in vscode.windows[0].model_dump()
    assert all(a.application_id != "notepad" for a in snap.applications)


def test_classifier_excludes_tray_and_tiny() -> None:
    api = FakeInventoryApi()
    api.windows[1] = {
        "title": "",
        "pid": 1,
        "visible": True,
        "class": "Shell_TrayWnd",
        "rect": (0, 0, 1920, 40),
    }
    api.windows[2] = {
        "title": "x",
        "pid": 1,
        "visible": True,
        "class": "X",
        "rect": (0, 0, 10, 10),
    }
    assert not is_useful_top_level_window(api, 1)
    assert not is_useful_top_level_window(api, 2)


def test_switcher_focus_and_limited() -> None:
    api = FakeInventoryApi()
    api.windows[10] = {
        "title": "a",
        "pid": 1,
        "visible": True,
        "minimized": True,
        "class": "X",
        "rect": (0, 0, 100, 100),
    }
    store = OpaqueWindowIdStore()
    binding = store.upsert(hwnd=10, application_id="vscode", process_id=1)
    switcher = WindowSwitcher(api=api, store=store)
    result = switcher.focus(binding.window_id)
    assert result.result in {FocusResultCode.FOCUSED, FocusResultCode.RESTORED}
    assert result.restored is True

    api.windows[10]["deny_focus"] = True
    limited = switcher.focus(binding.window_id)
    assert limited.result == FocusResultCode.RUNNING_FOCUS_LIMITED
    assert limited.focus_limited is True


def test_stale_window_id_rejected() -> None:
    switcher = WindowSwitcher(api=FakeInventoryApi(), store=OpaqueWindowIdStore())
    result = switcher.focus("win_missing")
    assert result.result == FocusResultCode.WINDOW_NOT_FOUND
