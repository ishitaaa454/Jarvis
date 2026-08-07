"""Metric history store tests."""

import pytest

from app.services.system_monitor.metric_history_store import MetricHistoryStore


def test_history_is_bounded() -> None:
    store = MetricHistoryStore(max_samples=3)
    for i in range(10):
        store.push("cpu.usage_percent", float(i), float(i))
    assert store.sample_count("cpu.usage_percent") == 3


def test_rejects_nan_and_infinity() -> None:
    store = MetricHistoryStore()
    store.push("cpu.usage_percent", 1.0, float("nan"))
    store.push("cpu.usage_percent", 2.0, float("inf"))
    points = store.get("cpu.usage_percent")
    assert points[0].value is None
    assert points[1].value is None


def test_preserves_timestamps_and_empty() -> None:
    store = MetricHistoryStore()
    assert store.get("cpu.usage_percent") == []
    store.push("cpu.usage_percent", 10.0, 25.0)
    points = store.get("cpu.usage_percent")
    assert points[0].timestamp == 10.0
    assert points[0].value == 25.0


def test_point_limit_and_constant_series() -> None:
    store = MetricHistoryStore(max_samples=50)
    for i in range(20):
        store.push("memory.usage_percent", float(i), 50.0)
    points = store.get("memory.usage_percent", points=5)
    assert len(points) == 5
    assert all(p.value == 50.0 for p in points)


def test_unknown_metric_not_stored() -> None:
    store = MetricHistoryStore()
    store.push("not.a.metric", 1.0, 1.0)
    assert store.sample_count("not.a.metric") == 0


def test_max_samples_must_be_positive() -> None:
    with pytest.raises(ValueError):
        MetricHistoryStore(max_samples=0)
