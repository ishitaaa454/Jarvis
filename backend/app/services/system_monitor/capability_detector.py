"""Capability detection and change tracking."""

from __future__ import annotations

from app.models.system_metrics import (
    AvailabilityReason,
    BatteryMetrics,
    CapabilityReport,
    CapabilityStatus,
    CpuMetrics,
    DiskMetrics,
    GpuMetrics,
    MemoryMetrics,
    NetworkMetrics,
    ProcessSnapshot,
    TemperatureMetrics,
)


def _from_availability(
    available_flag: bool,
    *,
    provider: str | None,
    reason: str | None,
    code: AvailabilityReason,
    limited: bool = False,
) -> CapabilityStatus:
    return CapabilityStatus(
        available=available_flag,
        provider=provider,
        limited=limited,
        reason=reason,
        code=code,
    )


class CapabilityDetector:
    def __init__(self) -> None:
        self._last: CapabilityReport | None = None

    def build(
        self,
        *,
        cpu: CpuMetrics,
        memory: MemoryMetrics,
        disk: DiskMetrics,
        network: NetworkMetrics,
        battery: BatteryMetrics,
        gpu: GpuMetrics,
        temperatures: TemperatureMetrics,
        processes: ProcessSnapshot,
    ) -> CapabilityReport:
        report = CapabilityReport(
            cpu=_from_availability(
                cpu.availability == AvailabilityReason.AVAILABLE,
                provider="psutil",
                reason=None if cpu.availability == AvailabilityReason.AVAILABLE else cpu.availability.value,
                code=cpu.availability,
            ),
            memory=_from_availability(
                memory.availability == AvailabilityReason.AVAILABLE,
                provider="psutil",
                reason=None
                if memory.availability == AvailabilityReason.AVAILABLE
                else memory.availability.value,
                code=memory.availability,
            ),
            disk=_from_availability(
                disk.availability == AvailabilityReason.AVAILABLE,
                provider="psutil",
                reason=None if disk.availability == AvailabilityReason.AVAILABLE else disk.availability.value,
                code=disk.availability,
            ),
            network=_from_availability(
                network.availability
                in {AvailabilityReason.AVAILABLE, AvailabilityReason.DATA_PENDING},
                provider="psutil",
                reason=None
                if network.availability
                in {AvailabilityReason.AVAILABLE, AvailabilityReason.DATA_PENDING}
                else network.availability.value,
                code=network.availability,
            ),
            battery=_from_availability(
                battery.present and battery.availability == AvailabilityReason.AVAILABLE,
                provider="psutil",
                reason="No battery detected"
                if battery.availability == AvailabilityReason.NOT_DETECTED
                else (
                    None
                    if battery.availability == AvailabilityReason.AVAILABLE
                    else battery.availability.value
                ),
                code=battery.availability,
            ),
            gpu=_from_availability(
                gpu.availability == AvailabilityReason.AVAILABLE,
                provider=gpu.provider,
                reason=gpu.reason,
                code=gpu.availability,
            ),
            temperatures=_from_availability(
                temperatures.availability == AvailabilityReason.AVAILABLE,
                provider=temperatures.provider,
                reason=temperatures.reason,
                code=temperatures.availability,
            ),
            processes=_from_availability(
                processes.availability
                in {AvailabilityReason.AVAILABLE, AvailabilityReason.PERMISSION_LIMITED},
                provider="psutil",
                reason="Some protected processes cannot be inspected"
                if processes.limited_count
                else None,
                code=processes.availability,
                limited=processes.limited_count > 0,
            ),
        )
        return report

    def changed(self, report: CapabilityReport) -> bool:
        if self._last is None:
            self._last = report
            return True
        if report.model_dump() != self._last.model_dump():
            self._last = report
            return True
        return False
