"""Central SystemMonitorService — single scheduler for Phase 6 metrics."""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.core.events import (
    SYSTEM_CAPABILITIES_CHANGED,
    SYSTEM_METRICS,
    SYSTEM_MONITOR_ERROR,
    SYSTEM_MONITOR_STATUS,
    SYSTEM_MONITOR_WARNING,
    SYSTEM_PROCESSES_UPDATED,
    EventBus,
)
from app.models.system_metrics import (
    AvailabilityReason,
    CapabilityReport,
    MonitorServiceStatus,
    ProcessSnapshot,
    ProviderError,
    SystemMonitorSnapshot,
    SystemMonitorStatusResponse,
)
from app.services.system_monitor.battery_provider import BatteryProvider
from app.services.system_monitor.capability_detector import CapabilityDetector
from app.services.system_monitor.cpu_provider import CpuProvider
from app.services.system_monitor.disk_provider import DiskProvider
from app.services.system_monitor.gpu_provider import GpuProvider, NvidiaGpuProvider
from app.services.system_monitor.memory_provider import MemoryProvider
from app.services.system_monitor.metric_history_store import ALLOWED_METRICS, MetricHistoryStore
from app.services.system_monitor.metric_rate_calculator import MetricRateCalculator
from app.services.system_monitor.network_provider import NetworkProvider
from app.services.system_monitor.process_provider import ProcessProvider
from app.services.system_monitor.system_info_provider import SystemInfoProvider
from app.services.system_monitor.temperature_provider import TemperatureProvider

logger = logging.getLogger(__name__)


class SystemMonitorService:
    def __init__(
        self,
        settings: Settings,
        event_bus: EventBus | None = None,
        *,
        executor: ThreadPoolExecutor | None = None,
        cpu: CpuProvider | None = None,
        memory: MemoryProvider | None = None,
        disk: DiskProvider | None = None,
        network: NetworkProvider | None = None,
        battery: BatteryProvider | None = None,
        processes: ProcessProvider | None = None,
        system_info: SystemInfoProvider | None = None,
        gpu: GpuProvider | None = None,
        temperatures: TemperatureProvider | None = None,
        history: MetricHistoryStore | None = None,
    ) -> None:
        self._settings = settings
        self._bus = event_bus
        self._executor = executor or ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="system-monitor"
        )
        self._own_executor = executor is None
        rates = MetricRateCalculator()
        self._cpu = cpu or CpuProvider()
        self._memory = memory or MemoryProvider()
        self._disk = disk or DiskProvider(
            rates=rates,
            include_network=settings.system_include_network_drives,
            include_removable=settings.system_include_removable_drives,
        )
        self._network = network or NetworkProvider(
            rates=rates,
            include_loopback=settings.system_include_loopback_adapters,
            include_disconnected=settings.system_include_disconnected_adapters,
            include_virtual=settings.system_include_virtual_adapters,
            show_ip=settings.system_show_ip_addresses,
        )
        self._battery = battery or BatteryProvider()
        self._processes = processes or ProcessProvider()
        self._system_info = system_info or SystemInfoProvider(
            backend_version=settings.app_version,
            show_hostname=settings.system_show_hostname,
        )
        nvidia = NvidiaGpuProvider(
            enabled=settings.gpu_monitor_enabled and settings.nvidia_nvml_enabled
        )
        self._gpu = gpu or GpuProvider(nvidia=nvidia)
        self._temperatures = temperatures or TemperatureProvider(
            enabled=settings.temperature_monitor_enabled,
            libre_enabled=settings.libre_hardware_monitor_enabled,
            libre_path=settings.libre_hardware_monitor_path,
        )
        self._history = history or MetricHistoryStore(settings.system_history_max_samples)
        self._capabilities = CapabilityDetector()

        self._status = MonitorServiceStatus.STOPPED
        self._started_at: datetime | None = None
        self._last_fast: datetime | None = None
        self._last_process: datetime | None = None
        self._last_static: datetime | None = None
        self._provider_errors: list[ProviderError] = []
        self._snapshot: SystemMonitorSnapshot | None = None
        self._process_snapshot = ProcessSnapshot()
        self._capability_report: CapabilityReport | None = None
        self._task: asyncio.Task[None] | None = None
        self._sampling = False
        self._refresh_requested = False
        self._lock = asyncio.Lock()

    def bind(self, event_bus: EventBus) -> None:
        self._bus = event_bus

    @property
    def status(self) -> MonitorServiceStatus:
        return self._status

    def get_status(self) -> SystemMonitorStatusResponse:
        return SystemMonitorStatusResponse(
            enabled=self._settings.system_monitor_enabled,
            status=self._status,
            started_at=self._started_at,
            last_fast_sample_at=self._last_fast,
            last_process_sample_at=self._last_process,
            last_static_refresh_at=self._last_static,
            history_samples=self._history.sample_count(),
            degraded=self._status == MonitorServiceStatus.DEGRADED,
            provider_errors=list(self._provider_errors),
        )

    def get_snapshot(self) -> SystemMonitorSnapshot:
        if self._snapshot is not None:
            return self._snapshot
        return SystemMonitorSnapshot(
            timestamp=datetime.now(timezone.utc),
            status=self._status,
            capabilities=self._capability_report,
        )

    def get_processes(self) -> ProcessSnapshot:
        return self._process_snapshot

    def get_capabilities(self) -> CapabilityReport | None:
        return self._capability_report

    def get_history(self, metric: str, points: int | None = None) -> list[dict[str, Any]]:
        if metric not in ALLOWED_METRICS and not metric.startswith("cpu.core."):
            raise ValueError(f"Unknown metric: {metric}")
        max_points = self._settings.system_history_max_api_points
        series = self._history.get(metric, points=points, max_points=max_points)
        return [{"timestamp": p.timestamp, "value": p.value} for p in series]

    async def on_startup(self) -> None:
        if not self._settings.system_monitor_enabled:
            self._status = MonitorServiceStatus.DISABLED
            await self._publish_status()
            return
        if not self._settings.system_monitor_start_automatically:
            self._status = MonitorServiceStatus.STOPPED
            await self._publish_status()
            return
        await self.start()

    async def start(self) -> None:
        async with self._lock:
            if self._task and not self._task.done():
                return
            if not self._settings.system_monitor_enabled:
                self._status = MonitorServiceStatus.DISABLED
                await self._publish_status()
                return
            self._status = MonitorServiceStatus.STARTING
            self._started_at = datetime.now(timezone.utc)
            await self._publish_status()
            # Warm CPU sampler once.
            await self._run_blocking(lambda: self._cpu.collect())
            await self._sample(fast=True, processes=True, static=True, optional=True)
            self._status = (
                MonitorServiceStatus.DEGRADED
                if self._provider_errors
                else MonitorServiceStatus.RUNNING
            )
            await self._publish_status()
            self._task = asyncio.create_task(self._loop(), name="system-monitor-loop")
            logger.info("System monitor started (%s)", self._status.value)

    async def stop(self) -> None:
        async with self._lock:
            if self._status in {
                MonitorServiceStatus.STOPPED,
                MonitorServiceStatus.DISABLED,
            }:
                return
            self._status = MonitorServiceStatus.STOPPING
            await self._publish_status()
            task = self._task
            self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        try:
            self._gpu.shutdown()
        except Exception:
            logger.debug("GPU provider shutdown failed", exc_info=True)
        self._status = MonitorServiceStatus.STOPPED
        await self._publish_status()
        logger.info("System monitor stopped")

    async def shutdown(self) -> None:
        await self.stop()
        if self._own_executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    async def request_refresh(self) -> SystemMonitorStatusResponse:
        self._refresh_requested = True
        return self.get_status()

    async def retry_provider(self, provider_name: str) -> SystemMonitorStatusResponse:
        allowed = {"gpu", "temperatures", "battery", "network", "disk"}
        if provider_name not in allowed:
            raise ValueError("Unknown provider")
        self._provider_errors = [
            err for err in self._provider_errors if err.provider != provider_name
        ]
        await self._sample(
            fast=provider_name in {"battery", "network", "disk"},
            processes=False,
            static=False,
            optional=provider_name in {"gpu", "temperatures"},
            only=provider_name,
        )
        return self.get_status()

    async def _loop(self) -> None:
        fast_i = self._settings.system_fast_sample_interval_seconds
        proc_i = self._settings.system_process_sample_interval_seconds
        static_i = self._settings.system_static_refresh_interval_seconds
        opt_i = self._settings.system_optional_hardware_interval_seconds
        next_fast = time.monotonic()
        next_proc = time.monotonic()
        next_static = time.monotonic() + static_i
        next_opt = time.monotonic() + opt_i
        try:
            while True:
                now = time.monotonic()
                do_fast = now >= next_fast or self._refresh_requested
                do_proc = now >= next_proc or self._refresh_requested
                do_static = now >= next_static
                do_opt = now >= next_opt or self._refresh_requested
                self._refresh_requested = False
                if do_fast or do_proc or do_static or do_opt:
                    await self._sample(
                        fast=do_fast,
                        processes=do_proc,
                        static=do_static,
                        optional=do_opt,
                    )
                    if do_fast:
                        next_fast = time.monotonic() + fast_i
                    if do_proc:
                        next_proc = time.monotonic() + proc_i
                    if do_static:
                        next_static = time.monotonic() + static_i
                    if do_opt:
                        next_opt = time.monotonic() + opt_i
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            raise

    async def _sample(
        self,
        *,
        fast: bool,
        processes: bool,
        static: bool,
        optional: bool,
        only: str | None = None,
    ) -> None:
        if self._sampling:
            return
        self._sampling = True
        errors: list[ProviderError] = []
        try:
            snap = self.get_snapshot()
            now = datetime.now(timezone.utc)
            stamp = time.time()

            async def collect(name: str, fn: Any, *, timeout: float | None = None) -> Any:
                try:
                    return await asyncio.wait_for(
                        self._run_blocking(fn),
                        timeout=timeout or self._settings.system_provider_timeout_seconds,
                    )
                except Exception as exc:
                    errors.append(
                        ProviderError(
                            provider=name,
                            code="PROVIDER_TIMEOUT"
                            if isinstance(exc, asyncio.TimeoutError)
                            else "PROVIDER_ERROR",
                            message=f"{name} provider failed",
                        )
                    )
                    logger.debug("Provider %s failed: %s", name, exc, exc_info=True)
                    return None

            if fast or only in {"battery", "network", "disk", None}:
                if only in {None, "disk"} or fast:
                    cpu = await collect("cpu", self._cpu.collect) if only is None else None
                    memory = await collect("memory", self._memory.collect) if only is None else None
                    disk = await collect("disk", self._disk.collect)
                    network = await collect("network", self._network.collect)
                    battery = await collect("battery", self._battery.collect)
                    if cpu is not None:
                        snap.cpu = cpu
                        self._history.push("cpu.usage_percent", stamp, cpu.usage_percent)
                        if cpu.per_core_percent:
                            for idx, value in enumerate(cpu.per_core_percent):
                                self._history.push(f"cpu.core.{idx}", stamp, value)
                    if memory is not None:
                        snap.memory = memory
                        self._history.push("memory.usage_percent", stamp, memory.usage_percent)
                        self._history.push("memory.swap_percent", stamp, memory.swap_percent)
                    if disk is not None:
                        snap.disks = disk
                        self._history.push(
                            "disk.read_bytes_per_second",
                            stamp,
                            disk.activity.read_bytes_per_second,
                        )
                        self._history.push(
                            "disk.write_bytes_per_second",
                            stamp,
                            disk.activity.write_bytes_per_second,
                        )
                    if network is not None:
                        snap.network = network
                        self._history.push(
                            "network.receive_bytes_per_second",
                            stamp,
                            network.receive_bytes_per_second,
                        )
                        self._history.push(
                            "network.send_bytes_per_second",
                            stamp,
                            network.send_bytes_per_second,
                        )
                    if battery is not None:
                        snap.battery = battery
                        if battery.present:
                            self._history.push("battery.percent", stamp, battery.percent)
                    if only is None and fast:
                        self._last_fast = now

            if processes and only is None:
                process_snap = await collect(
                    "processes",
                    lambda: self._processes.collect(
                        limit=self._settings.system_process_limit,
                        sort=self._settings.system_process_default_sort,
                        include_start_time=self._settings.system_process_include_start_time,
                    ),
                    timeout=self._settings.system_process_timeout_seconds,
                )
                if process_snap is not None:
                    self._process_snapshot = process_snap
                    self._last_process = now
                    if self._settings.system_websocket_process_events_enabled:
                        await self._publish(
                            SYSTEM_PROCESSES_UPDATED,
                            process_snap.model_dump(mode="json"),
                        )

            if static and only is None:
                info = await collect("system_info", self._system_info.collect)
                if info is not None:
                    snap.static = info
                    self._last_static = now

            if optional or only in {"gpu", "temperatures"}:
                if only in {None, "gpu"}:
                    gpu = await collect("gpu", self._gpu.collect)
                    if gpu is not None:
                        snap.gpu = gpu
                        if gpu.devices:
                            self._history.push(
                                "gpu.usage_percent", stamp, gpu.devices[0].usage_percent
                            )
                            self._history.push(
                                "gpu.memory_percent", stamp, gpu.devices[0].memory_percent
                            )
                            self._history.push(
                                "gpu.temperature_celsius",
                                stamp,
                                gpu.devices[0].temperature_celsius,
                            )
                        elif gpu.availability not in {
                            AvailabilityReason.AVAILABLE,
                            AvailabilityReason.NOT_DETECTED,
                            AvailabilityReason.PROVIDER_NOT_INSTALLED,
                            AvailabilityReason.UNSUPPORTED,
                        }:
                            errors.append(
                                ProviderError(
                                    provider="gpu",
                                    code=gpu.availability.value,
                                    message=gpu.reason or "GPU unavailable",
                                )
                            )
                if only in {None, "temperatures"}:
                    temps = await collect("temperatures", self._temperatures.collect)
                    if temps is not None:
                        snap.temperatures = temps
                        if temps.readings:
                            self._history.push(
                                "temperature.celsius",
                                stamp,
                                max(r.celsius for r in temps.readings),
                            )

            # Merge durable provider errors (optional missing is not an error).
            durable = [
                err
                for err in errors
                if err.provider not in {"gpu", "temperatures"}
                or err.code not in {"PROVIDER_NOT_INSTALLED", "UNSUPPORTED", "NOT_DETECTED"}
            ]
            # Keep prior optional errors that still apply.
            for err in self._provider_errors:
                if err.provider in {"gpu", "temperatures"} and all(
                    e.provider != err.provider for e in durable
                ):
                    # Re-evaluate from snapshot later.
                    pass
            self._provider_errors = durable

            if snap.gpu.availability == AvailabilityReason.UNAVAILABLE and snap.gpu.reason:
                if not any(e.provider == "gpu" for e in self._provider_errors):
                    self._provider_errors.append(
                        ProviderError(
                            provider="gpu",
                            code=snap.gpu.availability.value,
                            message=snap.gpu.reason,
                        )
                    )

            report = self._capabilities.build(
                cpu=snap.cpu,
                memory=snap.memory,
                disk=snap.disks,
                network=snap.network,
                battery=snap.battery,
                gpu=snap.gpu,
                temperatures=snap.temperatures,
                processes=self._process_snapshot,
            )
            if self._capabilities.changed(report):
                self._capability_report = report
                await self._publish(
                    SYSTEM_CAPABILITIES_CHANGED,
                    report.model_dump(mode="json"),
                )
            else:
                self._capability_report = report

            snap.timestamp = now
            snap.status = self._status
            snap.degraded = bool(self._provider_errors)
            snap.capabilities = self._capability_report
            self._snapshot = snap

            if self._status not in {
                MonitorServiceStatus.STOPPING,
                MonitorServiceStatus.STOPPED,
                MonitorServiceStatus.DISABLED,
                MonitorServiceStatus.STARTING,
            }:
                self._status = (
                    MonitorServiceStatus.DEGRADED
                    if self._provider_errors
                    else MonitorServiceStatus.RUNNING
                )

            if fast and only is None and self._settings.system_websocket_metrics_enabled:
                await self._publish(
                    SYSTEM_METRICS,
                    {
                        "cpu": snap.cpu.model_dump(mode="json"),
                        "memory": snap.memory.model_dump(mode="json"),
                        "disk_activity": snap.disks.activity.model_dump(mode="json"),
                        "network": {
                            **snap.network.model_dump(mode="json"),
                            "adapters": [],  # keep WS compact; use REST for adapters
                        },
                        "battery": snap.battery.model_dump(mode="json"),
                        "gpu": snap.gpu.model_dump(mode="json"),
                        "temperatures": snap.temperatures.model_dump(mode="json"),
                        "static": {
                            "uptime_seconds": snap.static.uptime_seconds,
                            "hostname": snap.static.hostname
                            if self._settings.system_show_hostname
                            else None,
                        },
                    },
                )
        finally:
            self._sampling = False

    async def _run_blocking(self, fn: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, fn)

    async def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._bus is None:
            return
        await self._bus.publish(event_type, payload)

    async def _publish_status(self) -> None:
        status = self.get_status()
        await self._publish(SYSTEM_MONITOR_STATUS, status.model_dump(mode="json"))
