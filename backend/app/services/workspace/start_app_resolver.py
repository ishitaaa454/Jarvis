"""Discover Windows Start Menu apps via a fixed PowerShell command.

The command line is a hard-coded constant with no user-controlled
interpolation, and is always executed with ``shell=False``. Results are
cached briefly to avoid re-invoking PowerShell for every application.
The command runner is injectable so tests never spawn a real process.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)

# Fixed argv — never built from user/config input, never run through a shell.
POWERSHELL_START_APPS_ARGS: tuple[str, ...] = (
    "powershell.exe",
    "-NoProfile",
    "-NonInteractive",
    "-Command",
    "Get-StartApps | ConvertTo-Json -Compress",
)

CommandRunner = Callable[[list[str], float], str]


@dataclass(frozen=True)
class StartApp:
    name: str
    app_id: str


def _default_runner(args: list[str], timeout: float) -> str:
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
        check=False,
    )
    return completed.stdout or ""


class StartAppResolver:
    def __init__(
        self,
        *,
        timeout_seconds: float = 8.0,
        cache_ttl_seconds: float = 60.0,
        runner: CommandRunner | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._cache_ttl = cache_ttl_seconds
        self._runner = runner or _default_runner
        self._cache: list[StartApp] | None = None
        self._cache_at: float = 0.0

    def _discover(self) -> list[StartApp]:
        try:
            output = self._runner(list(POWERSHELL_START_APPS_ARGS), self._timeout)
        except subprocess.TimeoutExpired:
            logger.warning("Start Apps discovery timed out")
            return []
        except Exception:
            logger.exception("Start Apps discovery failed")
            return []

        text = (output or "").strip()
        if not text:
            return []

        try:
            data = json.loads(text)
        except ValueError:
            logger.warning("Start Apps discovery returned non-JSON output")
            return []

        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return []

        apps: list[StartApp] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name") or "").strip()
            app_id = str(item.get("AppID") or "").strip()
            if name and app_id:
                apps.append(StartApp(name=name, app_id=app_id))
        return apps

    def list_apps(self, *, force_refresh: bool = False) -> list[StartApp]:
        now = time.monotonic()
        if (
            not force_refresh
            and self._cache is not None
            and (now - self._cache_at) < self._cache_ttl
        ):
            return self._cache

        apps = self._discover()
        self._cache = apps
        self._cache_at = now
        return apps

    def resolve(self, name: str) -> StartApp | None:
        if not name:
            return None
        needle = name.strip().lower()
        apps = self.list_apps()
        for app in apps:
            if app.name.strip().lower() == needle:
                return app
        for app in apps:
            if needle in app.name.strip().lower():
                return app
        return None

    def invalidate_cache(self) -> None:
        self._cache = None
        self._cache_at = 0.0
