"""Memory and swap metrics via psutil."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from app.models.system_metrics import AvailabilityReason, MemoryMetrics, safe_percent


class MemoryBackend(Protocol):
    def virtual_memory(self) -> object: ...

    def swap_memory(self) -> object: ...


class PsutilMemoryBackend:
    def virtual_memory(self) -> object:
        import psutil

        return psutil.virtual_memory()

    def swap_memory(self) -> object:
        import psutil

        return psutil.swap_memory()


class MemoryProvider:
    def __init__(self, backend: MemoryBackend | None = None) -> None:
        self._backend = backend or PsutilMemoryBackend()

    def collect(self) -> MemoryMetrics:
        now = datetime.now(timezone.utc)
        try:
            mem = self._backend.virtual_memory()
            metrics = MemoryMetrics(
                total_bytes=int(getattr(mem, "total", 0) or 0),
                used_bytes=int(getattr(mem, "used", 0) or 0),
                available_bytes=int(getattr(mem, "available", 0) or 0),
                usage_percent=safe_percent(getattr(mem, "percent", None)),
                collected_at=now,
                availability=AvailabilityReason.AVAILABLE,
            )
        except Exception:
            return MemoryMetrics(
                collected_at=now,
                availability=AvailabilityReason.UNAVAILABLE,
            )

        try:
            swap = self._backend.swap_memory()
            total = int(getattr(swap, "total", 0) or 0)
            if total <= 0:
                metrics.swap_availability = AvailabilityReason.NOT_DETECTED
            else:
                metrics.swap_total_bytes = total
                metrics.swap_used_bytes = int(getattr(swap, "used", 0) or 0)
                metrics.swap_free_bytes = int(getattr(swap, "free", 0) or 0)
                metrics.swap_percent = safe_percent(getattr(swap, "percent", None))
                metrics.swap_availability = AvailabilityReason.AVAILABLE
        except Exception:
            metrics.swap_availability = AvailabilityReason.UNAVAILABLE
        return metrics
