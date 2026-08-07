"""Pydantic models for Phase 6 system monitoring."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MonitorServiceStatus(str, Enum):
    DISABLED = "DISABLED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class AvailabilityReason(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNSUPPORTED = "UNSUPPORTED"
    UNAVAILABLE = "UNAVAILABLE"
    PERMISSION_LIMITED = "PERMISSION_LIMITED"
    NOT_DETECTED = "NOT_DETECTED"
    PROVIDER_NOT_INSTALLED = "PROVIDER_NOT_INSTALLED"
    DATA_PENDING = "DATA_PENDING"


class CapabilityStatus(BaseModel):
    available: bool
    provider: str | None = None
    limited: bool = False
    reason: str | None = None
    code: AvailabilityReason | None = None


class ProviderError(BaseModel):
    provider: str
    code: str
    message: str


class CpuMetrics(BaseModel):
    usage_percent: float | None = None
    per_core_percent: list[float] | None = None
    physical_cores: int | None = None
    logical_cores: int | None = None
    frequency_mhz: float | None = None
    frequency_min_mhz: float | None = None
    frequency_max_mhz: float | None = None
    architecture: str | None = None
    collected_at: datetime | None = None
    availability: AvailabilityReason = AvailabilityReason.AVAILABLE


class MemoryMetrics(BaseModel):
    total_bytes: int | None = None
    used_bytes: int | None = None
    available_bytes: int | None = None
    usage_percent: float | None = None
    swap_total_bytes: int | None = None
    swap_used_bytes: int | None = None
    swap_free_bytes: int | None = None
    swap_percent: float | None = None
    collected_at: datetime | None = None
    availability: AvailabilityReason = AvailabilityReason.AVAILABLE
    swap_availability: AvailabilityReason = AvailabilityReason.AVAILABLE


class DiskDriveMetrics(BaseModel):
    device: str
    mountpoint: str
    fstype: str | None = None
    total_bytes: int | None = None
    used_bytes: int | None = None
    free_bytes: int | None = None
    usage_percent: float | None = None
    read_only: bool | None = None


class DiskActivityMetrics(BaseModel):
    read_bytes_per_second: float | None = None
    write_bytes_per_second: float | None = None
    read_ops_per_second: float | None = None
    write_ops_per_second: float | None = None
    busy_percent: float | None = None
    collected_at: datetime | None = None
    availability: AvailabilityReason = AvailabilityReason.AVAILABLE


class DiskMetrics(BaseModel):
    drives: list[DiskDriveMetrics] = Field(default_factory=list)
    activity: DiskActivityMetrics = Field(default_factory=DiskActivityMetrics)
    collected_at: datetime | None = None
    availability: AvailabilityReason = AvailabilityReason.AVAILABLE


class NetworkAdapterMetrics(BaseModel):
    name: str
    is_up: bool | None = None
    speed_mbps: float | None = None
    mtu: int | None = None
    ipv4: str | None = None
    has_ipv6: bool | None = None
    bytes_recv: int | None = None
    bytes_sent: int | None = None


class NetworkMetrics(BaseModel):
    receive_bytes_per_second: float | None = None
    send_bytes_per_second: float | None = None
    bytes_recv_total: int | None = None
    bytes_sent_total: int | None = None
    adapters: list[NetworkAdapterMetrics] = Field(default_factory=list)
    active_adapter_count: int = 0
    collected_at: datetime | None = None
    availability: AvailabilityReason = AvailabilityReason.AVAILABLE


class BatteryStatus(str, Enum):
    CHARGING = "CHARGING"
    DISCHARGING = "DISCHARGING"
    FULL = "FULL"
    PLUGGED_IN = "PLUGGED_IN"
    UNKNOWN = "UNKNOWN"
    NOT_PRESENT = "NOT_PRESENT"


class BatteryMetrics(BaseModel):
    present: bool = False
    percent: float | None = None
    status: BatteryStatus = BatteryStatus.NOT_PRESENT
    power_plugged: bool | None = None
    secsleft: int | None = None
    secsleft_unknown: bool = False
    collected_at: datetime | None = None
    availability: AvailabilityReason = AvailabilityReason.NOT_DETECTED


class StaticSystemInfo(BaseModel):
    os_name: str | None = None
    os_release: str | None = None
    os_version: str | None = None
    architecture: str | None = None
    hostname: str | None = None
    python_version: str | None = None
    backend_version: str | None = None
    boot_time: datetime | None = None
    uptime_seconds: float | None = None
    physical_cores: int | None = None
    logical_cores: int | None = None
    collected_at: datetime | None = None


class GpuDeviceMetrics(BaseModel):
    index: int
    name: str
    usage_percent: float | None = None
    memory_used_bytes: int | None = None
    memory_total_bytes: int | None = None
    memory_percent: float | None = None
    temperature_celsius: float | None = None
    power_watts: float | None = None
    fan_speed_percent: float | None = None


class GpuMetrics(BaseModel):
    devices: list[GpuDeviceMetrics] = Field(default_factory=list)
    provider: str | None = None
    collected_at: datetime | None = None
    availability: AvailabilityReason = AvailabilityReason.PROVIDER_NOT_INSTALLED
    reason: str | None = "Optional NVIDIA monitoring is unavailable."


class TemperatureReading(BaseModel):
    category: str
    name: str
    celsius: float
    critical_celsius: float | None = None
    provider: str
    collected_at: datetime | None = None


class TemperatureMetrics(BaseModel):
    readings: list[TemperatureReading] = Field(default_factory=list)
    provider: str | None = None
    collected_at: datetime | None = None
    availability: AvailabilityReason = AvailabilityReason.PROVIDER_NOT_INSTALLED
    reason: str | None = "No supported temperature provider"


class ProcessRecord(BaseModel):
    pid: int
    name: str
    cpu_percent: float | None = None
    memory_percent: float | None = None
    memory_rss_bytes: int | None = None
    status: str | None = None
    create_time: float | None = None


class ProcessSnapshot(BaseModel):
    processes: list[ProcessRecord] = Field(default_factory=list)
    total_observed: int = 0
    returned: int = 0
    limited_count: int = 0
    collected_at: datetime | None = None
    availability: AvailabilityReason = AvailabilityReason.AVAILABLE


class CapabilityReport(BaseModel):
    cpu: CapabilityStatus
    memory: CapabilityStatus
    disk: CapabilityStatus
    network: CapabilityStatus
    battery: CapabilityStatus
    gpu: CapabilityStatus
    temperatures: CapabilityStatus
    processes: CapabilityStatus


class SystemMonitorSnapshot(BaseModel):
    timestamp: datetime
    cpu: CpuMetrics = Field(default_factory=CpuMetrics)
    memory: MemoryMetrics = Field(default_factory=MemoryMetrics)
    disks: DiskMetrics = Field(default_factory=DiskMetrics)
    network: NetworkMetrics = Field(default_factory=NetworkMetrics)
    battery: BatteryMetrics = Field(default_factory=BatteryMetrics)
    static: StaticSystemInfo = Field(default_factory=StaticSystemInfo)
    gpu: GpuMetrics = Field(default_factory=GpuMetrics)
    temperatures: TemperatureMetrics = Field(default_factory=TemperatureMetrics)
    status: MonitorServiceStatus = MonitorServiceStatus.STOPPED
    degraded: bool = False
    capabilities: CapabilityReport | None = None


class HistoryPoint(BaseModel):
    timestamp: float
    value: float | None = None


class HistorySeriesResponse(BaseModel):
    metric: str
    points: list[HistoryPoint] = Field(default_factory=list)
    series_id: str | None = None


class SystemMonitorStatusResponse(BaseModel):
    enabled: bool
    status: MonitorServiceStatus
    started_at: datetime | None = None
    last_fast_sample_at: datetime | None = None
    last_process_sample_at: datetime | None = None
    last_static_refresh_at: datetime | None = None
    history_samples: int = 0
    degraded: bool = False
    provider_errors: list[ProviderError] = Field(default_factory=list)


def safe_percent(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return max(0.0, min(100.0, number))


def safe_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number
