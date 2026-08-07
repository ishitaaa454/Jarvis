"""Disk capacity and aggregate I/O activity."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from app.models.system_metrics import (
    AvailabilityReason,
    DiskActivityMetrics,
    DiskDriveMetrics,
    DiskMetrics,
    safe_percent,
)
from app.services.system_monitor.metric_rate_calculator import MetricRateCalculator


class DiskBackend(Protocol):
    def disk_partitions(self, all: bool = False) -> list[object]: ...

    def disk_usage(self, path: str) -> object: ...

    def disk_io_counters(self) -> object | None: ...


class PsutilDiskBackend:
    def disk_partitions(self, all: bool = False) -> list[object]:
        import psutil

        return list(psutil.disk_partitions(all=all))

    def disk_usage(self, path: str) -> object:
        import psutil

        return psutil.disk_usage(path)

    def disk_io_counters(self) -> object | None:
        import psutil

        try:
            return psutil.disk_io_counters(perdisk=False)
        except Exception:
            return None


class DiskProvider:
    def __init__(
        self,
        backend: DiskBackend | None = None,
        rates: MetricRateCalculator | None = None,
        *,
        include_network: bool = False,
        include_removable: bool = False,
    ) -> None:
        self._backend = backend or PsutilDiskBackend()
        self._rates = rates or MetricRateCalculator()
        self._include_network = include_network
        self._include_removable = include_removable

    def _include_partition(self, part: object) -> bool:
        fstype = str(getattr(part, "fstype", "") or "").lower()
        opts = str(getattr(part, "opts", "") or "").lower()
        mount = str(getattr(part, "mountpoint", "") or "")
        if not mount or not fstype:
            return False
        if "cdrom" in opts or fstype in {"iso9660", "udf"}:
            return False
        if not self._include_removable and "removable" in opts:
            return False
        if not self._include_network and (
            fstype in {"nfs", "smbfs", "cifs"} or "remote" in opts
        ):
            return False
        return True

    def collect(self) -> DiskMetrics:
        now = datetime.now(timezone.utc)
        drives: list[DiskDriveMetrics] = []
        try:
            partitions = self._backend.disk_partitions(all=False)
        except Exception:
            return DiskMetrics(
                collected_at=now,
                availability=AvailabilityReason.UNAVAILABLE,
            )

        seen: set[str] = set()
        for part in partitions:
            if not self._include_partition(part):
                continue
            mount = str(getattr(part, "mountpoint", ""))
            if mount in seen:
                continue
            seen.add(mount)
            try:
                usage = self._backend.disk_usage(mount)
            except PermissionError:
                continue
            except Exception:
                continue
            opts = str(getattr(part, "opts", "") or "").lower()
            drives.append(
                DiskDriveMetrics(
                    device=str(getattr(part, "device", mount)),
                    mountpoint=mount,
                    fstype=str(getattr(part, "fstype", "") or None),
                    total_bytes=int(getattr(usage, "total", 0) or 0),
                    used_bytes=int(getattr(usage, "used", 0) or 0),
                    free_bytes=int(getattr(usage, "free", 0) or 0),
                    usage_percent=safe_percent(getattr(usage, "percent", None)),
                    read_only="read-only" in opts or "ro" in opts.split(","),
                )
            )

        activity = DiskActivityMetrics(collected_at=now)
        try:
            counters = self._backend.disk_io_counters()
            if counters is not None:
                read = self._rates.rate(
                    "disk.read_bytes", float(getattr(counters, "read_bytes", 0) or 0)
                )
                write = self._rates.rate(
                    "disk.write_bytes", float(getattr(counters, "write_bytes", 0) or 0)
                )
                read_ops = self._rates.rate(
                    "disk.read_count", float(getattr(counters, "read_count", 0) or 0)
                )
                write_ops = self._rates.rate(
                    "disk.write_count", float(getattr(counters, "write_count", 0) or 0)
                )
                activity.read_bytes_per_second = read.value if read.available else None
                activity.write_bytes_per_second = write.value if write.available else None
                activity.read_ops_per_second = read_ops.value if read_ops.available else None
                activity.write_ops_per_second = write_ops.value if write_ops.available else None
                if not read.available and not write.available:
                    activity.availability = AvailabilityReason.DATA_PENDING
            else:
                activity.availability = AvailabilityReason.UNAVAILABLE
        except Exception:
            activity.availability = AvailabilityReason.UNAVAILABLE

        return DiskMetrics(
            drives=drives,
            activity=activity,
            collected_at=now,
            availability=AvailabilityReason.AVAILABLE
            if drives
            else AvailabilityReason.UNAVAILABLE,
        )
