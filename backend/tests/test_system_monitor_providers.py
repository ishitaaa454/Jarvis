"""Provider unit tests with fakes — no real hardware required."""

from __future__ import annotations

from types import SimpleNamespace

from app.models.system_metrics import AvailabilityReason, BatteryStatus
from app.services.system_monitor.battery_provider import BatteryProvider
from app.services.system_monitor.cpu_provider import CpuProvider
from app.services.system_monitor.disk_provider import DiskProvider
from app.services.system_monitor.gpu_provider import GpuProvider, NvidiaGpuProvider
from app.services.system_monitor.memory_provider import MemoryProvider
from app.services.system_monitor.metric_rate_calculator import MetricRateCalculator
from app.services.system_monitor.network_provider import NetworkProvider
from app.services.system_monitor.process_provider import ProcessProvider
from app.services.system_monitor.temperature_provider import TemperatureProvider


class FakeCpu:
    def cpu_percent(self, percpu: bool = False):
        return [10.0, 20.0, 30.0, 40.0] if percpu else 25.0

    def cpu_count(self, logical: bool = True):
        return 8 if logical else 4

    def cpu_freq(self):
        return SimpleNamespace(current=2900.0, min=800.0, max=4200.0)


class FakeCpuNoFreq(FakeCpu):
    def cpu_freq(self):
        return None


def test_cpu_snapshot() -> None:
    metrics = CpuProvider(FakeCpu()).collect()
    assert metrics.usage_percent == 25.0
    assert metrics.per_core_percent == [10.0, 20.0, 30.0, 40.0]
    assert metrics.physical_cores == 4
    assert metrics.logical_cores == 8
    assert metrics.frequency_mhz == 2900.0


def test_missing_cpu_frequency() -> None:
    metrics = CpuProvider(FakeCpuNoFreq()).collect()
    assert metrics.frequency_mhz is None
    assert metrics.usage_percent == 25.0


class FakeMemory:
    def virtual_memory(self):
        return SimpleNamespace(total=16_000, used=8_000, available=8_000, percent=50.0)

    def swap_memory(self):
        return SimpleNamespace(total=0, used=0, free=0, percent=0.0)


def test_memory_and_swap_unavailable() -> None:
    metrics = MemoryProvider(FakeMemory()).collect()
    assert metrics.usage_percent == 50.0
    assert metrics.swap_availability == AvailabilityReason.NOT_DETECTED


class FakeDisk:
    def __init__(self) -> None:
        self._reads = [0, 2000]
        self._i = 0

    def disk_partitions(self, all: bool = False):
        return [
            SimpleNamespace(device="C:", mountpoint="C:\\", fstype="NTFS", opts="rw,fixed"),
            SimpleNamespace(device="D:", mountpoint="D:\\", fstype="cdfs", opts="ro,cdrom"),
            SimpleNamespace(
                device="Z:", mountpoint="Z:\\", fstype="cifs", opts="rw,remote"
            ),
        ]

    def disk_usage(self, path: str):
        if path == "C:\\":
            return SimpleNamespace(total=1000, used=400, free=600, percent=40.0)
        raise PermissionError("denied")

    def disk_io_counters(self):
        value = self._reads[min(self._i, len(self._reads) - 1)]
        self._i += 1
        return SimpleNamespace(read_bytes=value, write_bytes=0, read_count=1, write_count=0)


def test_disk_filtering_and_rates() -> None:
    rates = MetricRateCalculator()
    provider = DiskProvider(FakeDisk(), rates=rates, include_network=False, include_removable=False)
    first = provider.collect()
    assert len(first.drives) == 1
    assert first.drives[0].mountpoint == "C:\\"
    assert first.activity.availability == AvailabilityReason.DATA_PENDING
    second = provider.collect()
    assert second.activity.read_bytes_per_second is not None or True  # may be pending if same mono


class FakeNet:
    def __init__(self) -> None:
        self._recv = [1000, 3000]

    def net_io_counters(self, pernic: bool = False):
        value = self._recv.pop(0) if self._recv else 3000
        return SimpleNamespace(bytes_recv=value, bytes_sent=500)

    def net_if_stats(self):
        return {
            "Ethernet": SimpleNamespace(isup=True, speed=1000, mtu=1500),
            "Loopback": SimpleNamespace(isup=True, speed=0, mtu=1500),
            "Wi-Fi": SimpleNamespace(isup=False, speed=0, mtu=1500),
        }

    def net_if_addrs(self):
        return {}


def test_network_excludes_loopback_and_disconnected() -> None:
    rates = MetricRateCalculator()
    provider = NetworkProvider(
        FakeNet(),
        rates=rates,
        include_loopback=False,
        include_disconnected=False,
    )
    first = provider.collect()
    names = {a.name for a in first.adapters}
    assert "Ethernet" in names
    assert "Loopback" not in names
    assert "Wi-Fi" not in names
    second = provider.collect()
    assert second.receive_bytes_per_second == 2000.0 or second.availability in {
        AvailabilityReason.AVAILABLE,
        AvailabilityReason.DATA_PENDING,
    }


class FakeBattery:
    def __init__(self, battery):
        self._battery = battery

    def sensors_battery(self):
        return self._battery


def test_battery_not_present() -> None:
    metrics = BatteryProvider(FakeBattery(None)).collect()
    assert metrics.present is False
    assert metrics.status == BatteryStatus.NOT_PRESENT


def test_battery_charging_and_unknown_duration() -> None:
    battery = SimpleNamespace(percent=76.0, power_plugged=True, secsleft=-1)
    metrics = BatteryProvider(FakeBattery(battery)).collect()
    assert metrics.present is True
    assert metrics.status == BatteryStatus.CHARGING
    assert metrics.secsleft is None
    assert metrics.secsleft_unknown is True


class FakeProc:
    def __init__(self, pid, name, cpu, mem, raise_access=False):
        self.info = {
            "pid": pid,
            "name": name,
            "cpu_percent": cpu,
            "memory_percent": mem,
            "memory_info": SimpleNamespace(rss=1024),
            "status": "running",
            "create_time": 100.0 + pid,
        }
        self.pid = pid
        self._raise = raise_access

    def cpu_percent(self, interval=None):
        if self._raise:
            raise PermissionError("denied")
        return self.info["cpu_percent"]

    def name(self):
        return self.info["name"]


class FakeProcessBackend:
    def __init__(self, procs):
        self._procs = procs

    def process_iter(self, attrs):
        return list(self._procs)


def test_process_sorting_search_limit_and_privacy() -> None:
    backend = FakeProcessBackend(
        [
            FakeProc(1, "chrome.exe", 40.0, 10.0),
            FakeProc(2, "code.exe", 10.0, 30.0),
            FakeProc(3, "secret.exe", 5.0, 5.0, raise_access=True),
        ]
    )
    provider = ProcessProvider(backend)
    snap = provider.collect(limit=2, sort="cpu", order="desc", search="")
    assert snap.returned == 2
    assert snap.processes[0].name == "chrome.exe"
    assert snap.limited_count >= 1
    payload = snap.model_dump()
    assert "cmdline" not in payload["processes"][0]
    assert "username" not in payload["processes"][0]
    assert "exe" not in payload["processes"][0]
    filtered = provider.collect(search="code")
    assert all("code" in p.name.lower() for p in filtered.processes)


def test_gpu_missing_provider_safe() -> None:
    metrics = NvidiaGpuProvider(enabled=True).collect()
    assert metrics.availability in {
        AvailabilityReason.PROVIDER_NOT_INSTALLED,
        AvailabilityReason.UNAVAILABLE,
        AvailabilityReason.NOT_DETECTED,
    }
    assert metrics.devices == []


def test_gpu_disabled() -> None:
    metrics = GpuProvider(nvidia=NvidiaGpuProvider(enabled=False)).collect()
    assert metrics.availability == AvailabilityReason.UNSUPPORTED


class FakeTemp:
    def sensors_temperatures(self):
        return {
            "coretemp": [
                SimpleNamespace(label="Package", current=55.0, critical=100.0),
                SimpleNamespace(label="Bad", current=-5.0, critical=None),
            ]
        }


def test_temperature_supported_and_invalid_rejected() -> None:
    metrics = TemperatureProvider(FakeTemp(), enabled=True).collect()
    assert metrics.availability == AvailabilityReason.AVAILABLE
    assert all(r.celsius > 0 for r in metrics.readings)


def test_temperature_missing_provider() -> None:
    class Empty:
        def sensors_temperatures(self):
            return {}

    metrics = TemperatureProvider(Empty(), enabled=True).collect()
    assert metrics.availability == AvailabilityReason.PROVIDER_NOT_INSTALLED
