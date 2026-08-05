"""Process discovery by name via psutil, injectable for tests.

Never terminates or signals processes — discovery only. Handles per-process
AccessDenied/NoSuchProcess/ZombieProcess without failing the whole scan.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str


class PsutilModule(Protocol):
    """Minimal protocol so tests can inject a fake psutil module."""

    def process_iter(self, attrs: list[str] | None = None) -> Any: ...


class ProcessManager:
    """Read-only process discovery. Never kills or signals processes."""

    def __init__(self, psutil_module: PsutilModule | None = None) -> None:
        self._psutil = psutil_module

    def _load_psutil(self) -> PsutilModule:
        if self._psutil is not None:
            return self._psutil
        import psutil

        self._psutil = psutil
        return psutil

    def find_by_names(self, names: list[str]) -> list[ProcessInfo]:
        """Return running processes whose name matches (case-insensitive)."""
        if not names:
            return []
        needles = {n.strip().lower() for n in names if n.strip()}
        if not needles:
            return []

        try:
            psutil = self._load_psutil()
        except Exception:
            logger.exception("psutil is not available; process discovery disabled")
            return []

        try:
            iterator = psutil.process_iter(["pid", "name"])
        except Exception:
            logger.exception("Failed to enumerate processes")
            return []

        results: list[ProcessInfo] = []
        for proc in iterator:
            try:
                info = getattr(proc, "info", None)
                if info is None:
                    name = str(proc.name())
                    pid = int(proc.pid)
                else:
                    name = str(info.get("name") or "")
                    pid = int(info.get("pid"))
            except Exception:
                # Covers psutil.AccessDenied / NoSuchProcess / ZombieProcess
                # and any malformed process entry — skip and continue scanning.
                continue

            if name.strip().lower() in needles:
                results.append(ProcessInfo(pid=pid, name=name))
        return results

    def is_running(self, names: list[str]) -> bool:
        return bool(self.find_by_names(names))
