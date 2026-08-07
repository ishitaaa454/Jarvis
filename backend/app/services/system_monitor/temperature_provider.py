"""Optional temperature monitoring (psutil sensors + LibreHardwareMonitor stub)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from app.models.system_metrics import (
    AvailabilityReason,
    TemperatureMetrics,
    TemperatureReading,
    safe_number,
)


class TemperatureBackend(Protocol):
    def sensors_temperatures(self) -> dict[str, list[object]]: ...


class PsutilTemperatureBackend:
    def sensors_temperatures(self) -> dict[str, list[object]]:
        import psutil

        if not hasattr(psutil, "sensors_temperatures"):
            return {}
        data = psutil.sensors_temperatures() or {}
        return dict(data)


def _categorize(chip: str, label: str) -> str:
    text = f"{chip} {label}".lower()
    if "gpu" in text or "nvidia" in text or "amd" in text:
        return "GPU"
    if "cpu" in text or "core" in text or "package" in text:
        return "CPU"
    if "ssd" in text or "nvme" in text or "hdd" in text or "drive" in text:
        return "Storage"
    if "board" in text or "pch" in text or "acpitz" in text:
        return "Motherboard"
    return "Other"


class TemperatureProvider:
    def __init__(
        self,
        backend: TemperatureBackend | None = None,
        *,
        enabled: bool = True,
        libre_enabled: bool = False,
        libre_path: str = "",
    ) -> None:
        self._backend = backend or PsutilTemperatureBackend()
        self._enabled = enabled
        self._libre_enabled = libre_enabled
        self._libre_path = libre_path.strip()

    def collect(self) -> TemperatureMetrics:
        now = datetime.now(timezone.utc)
        if not self._enabled:
            return TemperatureMetrics(
                collected_at=now,
                availability=AvailabilityReason.UNSUPPORTED,
                reason="Temperature monitoring disabled by configuration",
            )

        readings: list[TemperatureReading] = []
        try:
            sensors = self._backend.sensors_temperatures()
        except Exception:
            sensors = {}

        for chip, entries in sensors.items():
            for entry in entries:
                label = str(getattr(entry, "label", "") or chip)
                current = safe_number(getattr(entry, "current", None))
                if current is None or current <= 0 or current > 150:
                    continue
                critical = safe_number(getattr(entry, "critical", None))
                readings.append(
                    TemperatureReading(
                        category=_categorize(chip, label),
                        name=label or chip,
                        celsius=current,
                        critical_celsius=critical,
                        provider="psutil",
                        collected_at=now,
                    )
                )

        if readings:
            # Prefer one reading per category to avoid noisy duplicates.
            preferred: dict[str, TemperatureReading] = {}
            for reading in readings:
                existing = preferred.get(reading.category)
                if existing is None or reading.celsius > existing.celsius:
                    preferred[reading.category] = reading
            return TemperatureMetrics(
                readings=list(preferred.values()),
                provider="psutil",
                collected_at=now,
                availability=AvailabilityReason.AVAILABLE,
                reason=None,
            )

        if self._libre_enabled and self._libre_path:
            return TemperatureMetrics(
                collected_at=now,
                availability=AvailabilityReason.UNAVAILABLE,
                reason="LibreHardwareMonitor configured but no readable sensors found",
                provider="libre-hardware-monitor",
            )

        return TemperatureMetrics(
            collected_at=now,
            availability=AvailabilityReason.PROVIDER_NOT_INSTALLED,
            reason="No supported temperature provider",
        )
