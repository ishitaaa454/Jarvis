"""Unit tests for MetricRateCalculator."""

from app.services.system_monitor.metric_rate_calculator import MetricRateCalculator


def test_first_sample_unavailable() -> None:
    calc = MetricRateCalculator()
    sample = calc.rate("net", 1000.0, now=1.0)
    assert sample.available is False
    assert sample.reason == "first_sample"


def test_rate_uses_monotonic_delta() -> None:
    calc = MetricRateCalculator()
    calc.rate("net", 1000.0, now=1.0)
    sample = calc.rate("net", 3000.0, now=3.0)
    assert sample.available is True
    assert sample.value == 1000.0


def test_zero_elapsed_unavailable() -> None:
    calc = MetricRateCalculator()
    calc.rate("net", 1000.0, now=1.0)
    sample = calc.rate("net", 2000.0, now=1.0)
    assert sample.available is False
    assert sample.reason == "zero_elapsed"


def test_negative_delta_is_reset() -> None:
    calc = MetricRateCalculator()
    calc.rate("net", 5000.0, now=1.0)
    sample = calc.rate("net", 1000.0, now=2.0)
    assert sample.available is False
    assert sample.reason == "counter_reset"


def test_rejects_nan_and_inf() -> None:
    calc = MetricRateCalculator()
    assert calc.rate("net", float("nan"), now=1.0).available is False
    assert calc.rate("net", float("inf"), now=1.0).available is False
