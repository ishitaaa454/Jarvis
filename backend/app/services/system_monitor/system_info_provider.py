"""Static system information provider."""

from __future__ import annotations

import platform
import socket
import sys
import time
from datetime import datetime, timezone

from app.models.system_metrics import StaticSystemInfo


class SystemInfoProvider:
    def __init__(self, *, backend_version: str = "0.1.0", show_hostname: bool = True) -> None:
        self._backend_version = backend_version
        self._show_hostname = show_hostname

    def collect(self) -> StaticSystemInfo:
        now = datetime.now(timezone.utc)
        boot_time = None
        uptime = None
        physical = logical = None
        try:
            import psutil

            boot = psutil.boot_time()
            boot_time = datetime.fromtimestamp(boot, tz=timezone.utc)
            uptime = max(0.0, time.time() - boot)
            physical = psutil.cpu_count(logical=False)
            logical = psutil.cpu_count(logical=True)
        except Exception:
            pass

        hostname = None
        if self._show_hostname:
            try:
                hostname = socket.gethostname()
            except Exception:
                hostname = None

        return StaticSystemInfo(
            os_name=platform.system() or None,
            os_release=platform.release() or None,
            os_version=platform.version() or None,
            architecture=platform.machine() or None,
            hostname=hostname,
            python_version=sys.version.split()[0],
            backend_version=self._backend_version,
            boot_time=boot_time,
            uptime_seconds=uptime,
            physical_cores=physical,
            logical_cores=logical,
            collected_at=now,
        )
