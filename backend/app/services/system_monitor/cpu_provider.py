"""CPU metrics via psutil (injectable for tests)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from app.models.system_metrics import AvailabilityReason, CpuMetrics, safe_number, safe_percent


class CpuBackend(Protocol):
    def cpu_percent(self, percpu: bool = False) -> float | list[float]: ...

    def cpu_count(self, logical: bool = True) -> int | None: ...

    def cpu_freq(self) -> object | None: ...


class PsutilCpuBackend:
    def cpu_percent(self, percpu: bool = False) -> float | list[float]:
        import psutil

        return psutil.cpu_percent(interval=None, percpu=percpu)

    def cpu_count(self, logical: bool = True) -> int | None:
        import psutil

        return psutil.cpu_count(logical=logical)

    def cpu_freq(self) -> object | None:
        import psutil

        try:
            return psutil.cpu_freq()
        except Exception:
            return None


class CpuProvider:
    def __init__(self, backend: CpuBackend | None = None) -> None:
        self._backend = backend or PsutilCpuBackend()

    def collect(self) -> CpuMetrics:
        now = datetime.now(timezone.utc)
        try:
            overall = safe_percent(self._backend.cpu_percent(percpu=False))
            raw_cores = self._backend.cpu_percent(percpu=True)
            cores: list[float] | None = None
            if isinstance(raw_cores, list):
                cores = [safe_percent(v) or 0.0 for v in raw_cores]
            freq = self._backend.cpu_freq()
            freq_current = freq_min = freq_max = None
            if freq is not None:
                freq_current = safe_number(getattr(freq, "current", None))
                freq_min = safe_number(getattr(freq, "min", None))
                freq_max = safe_number(getattr(freq, "max", None))
            import platform as py_platform

            return CpuMetrics(
                usage_percent=overall,
                per_core_percent=cores,
                physical_cores=self._backend.cpu_count(logical=False),
                logical_cores=self._backend.cpu_count(logical=True),
                frequency_mhz=freq_current,
                frequency_min_mhz=freq_min,
                frequency_max_mhz=freq_max,
                architecture=py_platform.machine() or None,
                collected_at=now,
                availability=AvailabilityReason.AVAILABLE,
            )
        except Exception:
            return CpuMetrics(
                collected_at=now,
                availability=AvailabilityReason.UNAVAILABLE,
            )
