"""Optional GPU monitoring with NVIDIA NVML provider abstraction."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from app.models.system_metrics import (
    AvailabilityReason,
    GpuDeviceMetrics,
    GpuMetrics,
    safe_number,
    safe_percent,
)


class NvidiaBackend(Protocol):
    def initialize(self) -> None: ...

    def device_count(self) -> int: ...

    def device_name(self, index: int) -> str: ...

    def utilization(self, index: int) -> float | None: ...

    def memory(self, index: int) -> tuple[int | None, int | None]: ...

    def temperature(self, index: int) -> float | None: ...

    def power(self, index: int) -> float | None: ...

    def fan(self, index: int) -> float | None: ...

    def shutdown(self) -> None: ...


class PynvmlBackend:
    def __init__(self) -> None:
        import pynvml  # type: ignore

        self._nvml = pynvml
        self._handles: list[object] = []

    def initialize(self) -> None:
        self._nvml.nvmlInit()
        count = int(self._nvml.nvmlDeviceGetCount())
        self._handles = [self._nvml.nvmlDeviceGetHandleByIndex(i) for i in range(count)]

    def device_count(self) -> int:
        return len(self._handles)

    def device_name(self, index: int) -> str:
        name = self._nvml.nvmlDeviceGetName(self._handles[index])
        if isinstance(name, bytes):
            return name.decode("utf-8", errors="replace")
        return str(name)

    def utilization(self, index: int) -> float | None:
        try:
            util = self._nvml.nvmlDeviceGetUtilizationRates(self._handles[index])
            return safe_percent(getattr(util, "gpu", None))
        except Exception:
            return None

    def memory(self, index: int) -> tuple[int | None, int | None]:
        try:
            mem = self._nvml.nvmlDeviceGetMemoryInfo(self._handles[index])
            return int(mem.used), int(mem.total)
        except Exception:
            return None, None

    def temperature(self, index: int) -> float | None:
        try:
            temp = self._nvml.nvmlDeviceGetTemperature(
                self._handles[index], self._nvml.NVML_TEMPERATURE_GPU
            )
            return safe_number(temp)
        except Exception:
            return None

    def power(self, index: int) -> float | None:
        try:
            milliwatts = self._nvml.nvmlDeviceGetPowerUsage(self._handles[index])
            return safe_number(milliwatts / 1000.0)
        except Exception:
            return None

    def fan(self, index: int) -> float | None:
        try:
            return safe_percent(self._nvml.nvmlDeviceGetFanSpeed(self._handles[index]))
        except Exception:
            return None

    def shutdown(self) -> None:
        try:
            self._nvml.nvmlShutdown()
        except Exception:
            pass
        self._handles = []


class NvidiaGpuProvider:
    def __init__(self, backend: NvidiaBackend | None = None, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._backend = backend
        self._ready = False
        self._init_error: str | None = None

    def _ensure(self) -> bool:
        if not self._enabled:
            self._init_error = "GPU monitoring disabled by configuration"
            return False
        if self._ready:
            return True
        try:
            if self._backend is None:
                self._backend = PynvmlBackend()
            self._backend.initialize()
            self._ready = True
            self._init_error = None
            return True
        except ModuleNotFoundError:
            self._init_error = "NVML provider is not installed"
            return False
        except Exception as exc:
            self._init_error = f"NVML initialization failed: {exc.__class__.__name__}"
            return False

    def collect(self) -> GpuMetrics:
        now = datetime.now(timezone.utc)
        if not self._ensure() or self._backend is None:
            code = (
                AvailabilityReason.PROVIDER_NOT_INSTALLED
                if self._init_error and "not installed" in self._init_error.lower()
                else AvailabilityReason.UNAVAILABLE
            )
            if self._init_error and "disabled" in self._init_error.lower():
                code = AvailabilityReason.UNSUPPORTED
            return GpuMetrics(
                collected_at=now,
                availability=code,
                reason=self._init_error or "GPU data unavailable",
            )

        try:
            count = self._backend.device_count()
            if count <= 0:
                return GpuMetrics(
                    provider="nvidia-nvml",
                    collected_at=now,
                    availability=AvailabilityReason.NOT_DETECTED,
                    reason="No supported GPU detected",
                )
            devices: list[GpuDeviceMetrics] = []
            for index in range(count):
                used, total = self._backend.memory(index)
                mem_percent = None
                if used is not None and total and total > 0:
                    mem_percent = safe_percent((used / total) * 100.0)
                devices.append(
                    GpuDeviceMetrics(
                        index=index,
                        name=self._backend.device_name(index),
                        usage_percent=self._backend.utilization(index),
                        memory_used_bytes=used,
                        memory_total_bytes=total,
                        memory_percent=mem_percent,
                        temperature_celsius=self._backend.temperature(index),
                        power_watts=self._backend.power(index),
                        fan_speed_percent=self._backend.fan(index),
                    )
                )
            return GpuMetrics(
                devices=devices,
                provider="nvidia-nvml",
                collected_at=now,
                availability=AvailabilityReason.AVAILABLE,
                reason=None,
            )
        except Exception as exc:
            return GpuMetrics(
                provider="nvidia-nvml",
                collected_at=now,
                availability=AvailabilityReason.UNAVAILABLE,
                reason=f"GPU data unavailable ({exc.__class__.__name__})",
            )

    def shutdown(self) -> None:
        if self._backend is not None and self._ready:
            try:
                self._backend.shutdown()
            except Exception:
                pass
        self._ready = False


class GpuProvider:
    """Facade that currently supports NVIDIA only; AMD/Intel reserved for later."""

    def __init__(self, nvidia: NvidiaGpuProvider | None = None) -> None:
        self._nvidia = nvidia or NvidiaGpuProvider(enabled=False)

    def collect(self) -> GpuMetrics:
        return self._nvidia.collect()

    def shutdown(self) -> None:
        self._nvidia.shutdown()
