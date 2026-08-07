"""SystemMonitorService lifecycle and API tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.events import EventBus
from app.models.system_metrics import (
    AvailabilityReason,
    BatteryMetrics,
    BatteryStatus,
    CpuMetrics,
    DiskActivityMetrics,
    DiskMetrics,
    GpuMetrics,
    MemoryMetrics,
    NetworkMetrics,
    ProcessSnapshot,
    StaticSystemInfo,
    TemperatureMetrics,
)
from app.services.system_monitor.system_monitor_service import SystemMonitorService


class FixedCpu:
    def collect(self) -> CpuMetrics:
        return CpuMetrics(
            usage_percent=20.0,
            per_core_percent=[10.0, 30.0],
            physical_cores=2,
            logical_cores=2,
            collected_at=datetime.now(timezone.utc),
        )


class FixedMemory:
    def collect(self) -> MemoryMetrics:
        return MemoryMetrics(
            total_bytes=100,
            used_bytes=40,
            available_bytes=60,
            usage_percent=40.0,
            collected_at=datetime.now(timezone.utc),
        )


class FixedDisk:
    def collect(self) -> DiskMetrics:
        return DiskMetrics(
            drives=[],
            activity=DiskActivityMetrics(
                read_bytes_per_second=100.0,
                write_bytes_per_second=50.0,
                collected_at=datetime.now(timezone.utc),
            ),
            collected_at=datetime.now(timezone.utc),
        )


class FixedNetwork:
    def collect(self) -> NetworkMetrics:
        return NetworkMetrics(
            receive_bytes_per_second=200.0,
            send_bytes_per_second=80.0,
            collected_at=datetime.now(timezone.utc),
        )


class FixedBattery:
    def collect(self) -> BatteryMetrics:
        return BatteryMetrics(
            present=False,
            status=BatteryStatus.NOT_PRESENT,
            availability=AvailabilityReason.NOT_DETECTED,
            collected_at=datetime.now(timezone.utc),
        )


class FixedProcesses:
    def collect(self, **kwargs) -> ProcessSnapshot:
        return ProcessSnapshot(total_observed=1, returned=0, limited_count=0)


class FixedInfo:
    def collect(self) -> StaticSystemInfo:
        return StaticSystemInfo(os_name="Windows", uptime_seconds=100.0)


class FixedGpu:
    def collect(self) -> GpuMetrics:
        return GpuMetrics(
            availability=AvailabilityReason.PROVIDER_NOT_INSTALLED,
            reason="NVML provider is not installed",
        )

    def shutdown(self) -> None:
        return None


class FixedTemp:
    def collect(self) -> TemperatureMetrics:
        return TemperatureMetrics(
            availability=AvailabilityReason.PROVIDER_NOT_INSTALLED,
            reason="No supported temperature provider",
        )


def make_service(**kwargs) -> SystemMonitorService:
    settings = Settings(
        system_monitor_enabled=True,
        system_monitor_start_automatically=False,
        system_fast_sample_interval_seconds=0.05,
        system_process_sample_interval_seconds=0.2,
        system_static_refresh_interval_seconds=10,
        system_optional_hardware_interval_seconds=0.2,
        system_provider_timeout_seconds=2,
        nvidia_nvml_enabled=False,
    )
    return SystemMonitorService(
        settings=settings,
        event_bus=EventBus(),
        cpu=kwargs.get("cpu", FixedCpu()),
        memory=kwargs.get("memory", FixedMemory()),
        disk=kwargs.get("disk", FixedDisk()),
        network=kwargs.get("network", FixedNetwork()),
        battery=kwargs.get("battery", FixedBattery()),
        processes=kwargs.get("processes", FixedProcesses()),
        system_info=kwargs.get("system_info", FixedInfo()),
        gpu=kwargs.get("gpu", FixedGpu()),
        temperatures=kwargs.get("temperatures", FixedTemp()),
    )


@pytest.fixture
def client() -> TestClient:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_start_stop_idempotent() -> None:
    service = make_service()
    await service.start()
    await service.start()
    assert service.status.value in {"RUNNING", "DEGRADED"}
    await service.stop()
    await service.stop()
    assert service.status.value == "STOPPED"
    await service.shutdown()


@pytest.mark.asyncio
async def test_no_battery_keeps_running() -> None:
    service = make_service()
    await service.start()
    snap = service.get_snapshot()
    assert snap.battery.present is False
    assert service.status.value in {"RUNNING", "DEGRADED"}
    await service.shutdown()


@pytest.mark.asyncio
async def test_history_endpoint_allowlist(client: TestClient) -> None:
    bad = client.get("/api/system-monitor/history", params={"metric": "evil.path"})
    assert bad.status_code == 400
    ok = client.get("/api/system-monitor/history", params={"metric": "cpu.usage_percent"})
    assert ok.status_code == 200
    assert ok.json()["metric"] == "cpu.usage_percent"


def test_status_snapshot_capabilities_endpoints(client: TestClient) -> None:
    status = client.get("/api/system-monitor/status")
    assert status.status_code == 200
    body = status.json()
    assert "status" in body
    assert "provider_errors" in body

    snap = client.get("/api/system-monitor/snapshot")
    assert snap.status_code == 200
    assert "cpu" in snap.json()

    caps = client.get("/api/system-monitor/capabilities")
    assert caps.status_code == 200


def test_processes_validation(client: TestClient) -> None:
    bad_sort = client.get("/api/system-monitor/processes", params={"sort": "cmdline"})
    assert bad_sort.status_code == 400
    bad_order = client.get("/api/system-monitor/processes", params={"order": "sideways"})
    assert bad_order.status_code == 400
    ok = client.get("/api/system-monitor/processes", params={"limit": 5})
    assert ok.status_code == 200
    for proc in ok.json()["processes"]:
        assert "cmdline" not in proc
        assert "username" not in proc
        assert "exe" not in proc


def test_retry_unknown_provider_rejected(client: TestClient) -> None:
    response = client.post("/api/system-monitor/retry-provider/evil")
    assert response.status_code == 400


def test_disks_and_network_endpoints(client: TestClient) -> None:
    assert client.get("/api/system-monitor/disks").status_code == 200
    adapters = client.get("/api/system-monitor/network-adapters")
    assert adapters.status_code == 200
    for adapter in adapters.json()["adapters"]:
        assert "mac" not in adapter
        assert "mac_address" not in adapter


def test_refresh_accepted(client: TestClient) -> None:
    response = client.post("/api/system-monitor/refresh")
    assert response.status_code == 200
    assert response.json()["accepted"] is True
