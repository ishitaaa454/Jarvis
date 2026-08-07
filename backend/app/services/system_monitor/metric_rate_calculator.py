"""Monotonic-time rate calculator for cumulative counters."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class RateSample:
    value: float | None
    available: bool
    reason: str | None = None


class MetricRateCalculator:
    """Compute bytes/ops per second from cumulative counters.

    Uses ``time.monotonic()`` exclusively. First samples, counter resets,
    wraparounds, zero elapsed time, and non-finite values return unavailable.
    """

    def __init__(self) -> None:
        self._previous: dict[str, tuple[float, float]] = {}

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._previous.clear()
        else:
            self._previous.pop(key, None)

    def rate(
        self,
        key: str,
        cumulative: float | None,
        *,
        now: float | None = None,
    ) -> RateSample:
        if cumulative is None:
            return RateSample(None, False, "missing_counter")
        try:
            value = float(cumulative)
        except (TypeError, ValueError):
            return RateSample(None, False, "invalid_counter")
        if value != value or value in (float("inf"), float("-inf")):
            return RateSample(None, False, "non_finite_counter")
        if value < 0:
            return RateSample(None, False, "negative_counter")

        stamp = time.monotonic() if now is None else now
        previous = self._previous.get(key)
        self._previous[key] = (stamp, value)
        if previous is None:
            return RateSample(None, False, "first_sample")

        prev_stamp, prev_value = previous
        elapsed = stamp - prev_stamp
        if elapsed <= 0:
            return RateSample(None, False, "zero_elapsed")
        delta = value - prev_value
        if delta < 0:
            # Counter reset or wrap — skip this sample.
            return RateSample(None, False, "counter_reset")
        return RateSample(delta / elapsed, True)
