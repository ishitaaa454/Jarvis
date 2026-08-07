"""Read-only process sampling with privacy boundaries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from app.models.system_metrics import AvailabilityReason, ProcessRecord, ProcessSnapshot, safe_percent


class ProcessBackend(Protocol):
    def process_iter(self, attrs: list[str]): ...


class PsutilProcessBackend:
    def process_iter(self, attrs: list[str]):
        import psutil

        return psutil.process_iter(attrs)


class ProcessProvider:
    """Persistent process CPU sampler.

    First pass establishes baselines; subsequent collections return
    meaningful percentages. Never exposes command lines, paths, or usernames.
    """

    def __init__(self, backend: ProcessBackend | None = None) -> None:
        self._backend = backend or PsutilProcessBackend()
        self._primed = False

    def collect(
        self,
        *,
        limit: int = 100,
        sort: str = "cpu",
        order: str = "desc",
        search: str = "",
        include_start_time: bool = True,
    ) -> ProcessSnapshot:
        now = datetime.now(timezone.utc)
        limited = 0
        observed = 0
        records: list[ProcessRecord] = []
        attrs = ["pid", "name", "cpu_percent", "memory_percent", "memory_info", "status"]
        if include_start_time:
            attrs.append("create_time")

        try:
            iterator = self._backend.process_iter(attrs)
        except Exception:
            return ProcessSnapshot(
                collected_at=now,
                availability=AvailabilityReason.UNAVAILABLE,
            )

        for proc in iterator:
            observed += 1
            try:
                info = proc.info if hasattr(proc, "info") else {}
                if hasattr(proc, "cpu_percent") and callable(proc.cpu_percent):
                    try:
                        cpu_val = proc.cpu_percent(interval=None)
                    except TypeError:
                        cpu_val = info.get("cpu_percent")
                    except Exception:
                        limited += 1
                        continue
                else:
                    cpu_val = info.get("cpu_percent")

                name = str(info.get("name") or "")
                if not name:
                    try:
                        name = str(proc.name())
                    except Exception:
                        name = f"pid-{info.get('pid', '?')}"

                mem_info = info.get("memory_info")
                rss = None
                if mem_info is not None:
                    rss = int(getattr(mem_info, "rss", 0) or 0)

                create_time = None
                if include_start_time and info.get("create_time") is not None:
                    create_time = float(info["create_time"])

                records.append(
                    ProcessRecord(
                        pid=int(info.get("pid") or getattr(proc, "pid", 0) or 0),
                        name=name,
                        cpu_percent=safe_percent(cpu_val),
                        memory_percent=safe_percent(info.get("memory_percent")),
                        memory_rss_bytes=rss,
                        status=str(info.get("status")) if info.get("status") else None,
                        create_time=create_time,
                    )
                )
            except Exception:
                limited += 1
                continue

        self._primed = True
        needle = search.strip().lower()
        if needle:
            records = [r for r in records if needle in r.name.lower()]

        reverse = order.lower() != "asc"
        key_map = {
            "cpu": lambda r: r.cpu_percent if r.cpu_percent is not None else -1.0,
            "memory": lambda r: r.memory_percent if r.memory_percent is not None else -1.0,
            "name": lambda r: r.name.lower(),
            "pid": lambda r: r.pid,
        }
        records.sort(key=key_map.get(sort.lower(), key_map["cpu"]), reverse=reverse)

        limit = max(1, min(int(limit), 100))
        clipped = records[:limit]
        return ProcessSnapshot(
            processes=clipped,
            total_observed=observed,
            returned=len(clipped),
            limited_count=limited,
            collected_at=now,
            availability=AvailabilityReason.AVAILABLE
            if limited == 0
            else AvailabilityReason.PERMISSION_LIMITED,
        )
