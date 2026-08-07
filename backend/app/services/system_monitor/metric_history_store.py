"""Bounded in-memory metric history for live session charts."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class HistoryPoint:
    timestamp: float
    value: float | None


ALLOWED_METRICS = frozenset(
    {
        "cpu.usage_percent",
        "memory.usage_percent",
        "memory.swap_percent",
        "disk.read_bytes_per_second",
        "disk.write_bytes_per_second",
        "network.receive_bytes_per_second",
        "network.send_bytes_per_second",
        "battery.percent",
        "gpu.usage_percent",
        "gpu.memory_percent",
        "gpu.temperature_celsius",
        "temperature.celsius",
    }
)


def is_finite_number(value: float | None) -> bool:
    if value is None:
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and number not in (float("inf"), float("-inf"))


class MetricHistoryStore:
    def __init__(self, max_samples: int = 300) -> None:
        if max_samples < 1:
            raise ValueError("max_samples must be >= 1")
        self._max = max_samples
        self._series: dict[str, deque[HistoryPoint]] = {}

    @property
    def max_samples(self) -> int:
        return self._max

    def sample_count(self, metric: str | None = None) -> int:
        if metric is None:
            if not self._series:
                return 0
            return max(len(points) for points in self._series.values())
        return len(self._series.get(metric, ()))

    def push(self, metric: str, timestamp: float, value: float | None) -> None:
        if metric not in ALLOWED_METRICS and not metric.startswith("cpu.core."):
            return
        if value is not None and not is_finite_number(value):
            value = None
        bucket = self._series.setdefault(metric, deque(maxlen=self._max))
        bucket.append(HistoryPoint(timestamp=timestamp, value=value))

    def get(
        self,
        metric: str,
        *,
        points: int | None = None,
        max_points: int = 300,
    ) -> list[HistoryPoint]:
        series = list(self._series.get(metric, ()))
        if not series:
            return []
        limit = max_points if points is None else max(1, min(points, max_points))
        if len(series) <= limit:
            return series
        # Downsample evenly while always keeping the newest point.
        step = len(series) / limit
        selected = [series[int(i * step)] for i in range(limit - 1)]
        selected.append(series[-1])
        return selected

    def clear(self) -> None:
        self._series.clear()

    def metrics(self) -> Iterable[str]:
        return tuple(self._series.keys())
