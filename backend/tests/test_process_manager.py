"""ProcessManager tests using a fake psutil module — never touches real processes."""

from __future__ import annotations

from app.services.workspace.process_manager import ProcessManager


class FakeProcess:
    def __init__(self, pid: int, name: str, *, raises: Exception | None = None) -> None:
        self.pid = pid
        self._name = name
        self._raises = raises
        self.info = {"pid": pid, "name": name}

    def name(self) -> str:
        if self._raises:
            raise self._raises
        return self._name


class FakePsutil:
    def __init__(self, processes: list[FakeProcess]) -> None:
        self._processes = processes

    def process_iter(self, attrs=None):
        return iter(self._processes)


class AccessDenied(Exception):
    pass


def test_find_by_names_matches_case_insensitively() -> None:
    fake = FakePsutil(
        [
            FakeProcess(111, "Code.exe"),
            FakeProcess(222, "chrome.exe"),
            FakeProcess(333, "notepad.exe"),
        ]
    )
    manager = ProcessManager(psutil_module=fake)
    results = manager.find_by_names(["CODE.EXE"])
    assert len(results) == 1
    assert results[0].pid == 111
    assert results[0].name == "Code.exe"


def test_find_by_names_returns_empty_for_no_match() -> None:
    fake = FakePsutil([FakeProcess(111, "notepad.exe")])
    manager = ProcessManager(psutil_module=fake)
    assert manager.find_by_names(["chrome.exe"]) == []


def test_find_by_names_empty_input_returns_empty() -> None:
    fake = FakePsutil([FakeProcess(111, "notepad.exe")])
    manager = ProcessManager(psutil_module=fake)
    assert manager.find_by_names([]) == []


def test_multiple_names_matched() -> None:
    fake = FakePsutil(
        [
            FakeProcess(1, "Teams.exe"),
            FakeProcess(2, "ms-teams.exe"),
            FakeProcess(3, "unrelated.exe"),
        ]
    )
    manager = ProcessManager(psutil_module=fake)
    results = manager.find_by_names(["Teams.exe", "ms-teams.exe"])
    assert {r.pid for r in results} == {1, 2}


def test_access_denied_on_individual_process_is_skipped() -> None:
    class Proc:
        def __init__(self, pid, name, raises=False):
            self.pid = pid
            self._name = name
            self._raises = raises

        @property
        def info(self):
            if self._raises:
                raise AccessDenied("no access")
            return {"pid": self.pid, "name": self._name}

    fake = FakePsutil([Proc(1, "chrome.exe", raises=True), Proc(2, "chrome.exe")])
    manager = ProcessManager(psutil_module=fake)
    results = manager.find_by_names(["chrome.exe"])
    assert len(results) == 1
    assert results[0].pid == 2


def test_process_iter_failure_returns_empty_list_not_raise() -> None:
    class BrokenPsutil:
        def process_iter(self, attrs=None):
            raise RuntimeError("enumeration failed")

    manager = ProcessManager(psutil_module=BrokenPsutil())
    assert manager.find_by_names(["chrome.exe"]) == []


def test_is_running_true_and_false() -> None:
    fake = FakePsutil([FakeProcess(1, "chrome.exe")])
    manager = ProcessManager(psutil_module=fake)
    assert manager.is_running(["chrome.exe"]) is True
    assert manager.is_running(["notepad.exe"]) is False


def test_never_terminates_processes() -> None:
    """ProcessManager exposes no kill/terminate capability at all."""
    assert not hasattr(ProcessManager, "kill")
    assert not hasattr(ProcessManager, "terminate")
