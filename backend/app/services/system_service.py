"""System metrics used by the health endpoint."""

from __future__ import annotations

import platform
from typing import Any

import psutil


class SystemService:
    """Collects basic host metrics for Phase 1 health reporting."""

    def get_basic_metrics(self) -> dict[str, Any]:
        """Return platform name plus live CPU and memory percentages."""
        # interval=None uses a non-blocking reading based on prior sample.
        cpu_percent = float(psutil.cpu_percent(interval=None))
        memory_percent = float(psutil.virtual_memory().percent)
        system_name = platform.system() or "Unknown"

        return {
            "platform": system_name,
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
        }
