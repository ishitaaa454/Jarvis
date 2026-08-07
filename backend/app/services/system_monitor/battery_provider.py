"""Battery / AC power status."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from app.models.system_metrics import AvailabilityReason, BatteryMetrics, BatteryStatus, safe_percent


class BatteryBackend(Protocol):
    def sensors_battery(self) -> object | None: ...


class PsutilBatteryBackend:
    def sensors_battery(self) -> object | None:
        import psutil

        try:
            return psutil.sensors_battery()
        except Exception:
            return None


class BatteryProvider:
    def __init__(self, backend: BatteryBackend | None = None) -> None:
        self._backend = backend or PsutilBatteryBackend()

    def collect(self) -> BatteryMetrics:
        now = datetime.now(timezone.utc)
        try:
            battery = self._backend.sensors_battery()
        except Exception:
            return BatteryMetrics(
                present=False,
                status=BatteryStatus.UNKNOWN,
                collected_at=now,
                availability=AvailabilityReason.UNAVAILABLE,
            )

        if battery is None:
            return BatteryMetrics(
                present=False,
                status=BatteryStatus.NOT_PRESENT,
                collected_at=now,
                availability=AvailabilityReason.NOT_DETECTED,
            )

        percent = safe_percent(getattr(battery, "percent", None))
        plugged = getattr(battery, "power_plugged", None)
        secsleft = getattr(battery, "secsleft", None)
        unknown = False
        try:
            import psutil

            if secsleft in (psutil.POWER_TIME_UNKNOWN, -1):
                secsleft = None
                unknown = True
            elif secsleft == getattr(psutil, "POWER_TIME_UNLIMITED", -2):
                secsleft = None
                unknown = False
        except Exception:
            if isinstance(secsleft, int) and secsleft < 0:
                secsleft = None
                unknown = True

        if plugged is True and percent is not None and percent >= 99.5:
            status = BatteryStatus.FULL
        elif plugged is True:
            status = BatteryStatus.CHARGING
        elif plugged is False:
            status = BatteryStatus.DISCHARGING
        else:
            status = BatteryStatus.UNKNOWN

        return BatteryMetrics(
            present=True,
            percent=percent,
            status=status,
            power_plugged=bool(plugged) if plugged is not None else None,
            secsleft=int(secsleft) if isinstance(secsleft, (int, float)) else None,
            secsleft_unknown=unknown,
            collected_at=now,
            availability=AvailabilityReason.AVAILABLE,
        )
