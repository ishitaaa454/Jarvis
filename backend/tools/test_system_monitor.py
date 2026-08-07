#!/usr/bin/env python3
"""Manual Phase 6 system-monitor tool using production providers."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.services.system_monitor import SystemMonitorService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test Jarvis system monitoring.")
    parser.add_argument("--capabilities", action="store_true")
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--processes", action="store_true")
    parser.add_argument("--disks", action="store_true")
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--temperatures", action="store_true")
    parser.add_argument("--seconds", type=float, default=30.0)
    return parser.parse_args()


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "UNAVAILABLE"
    return f"{value:.1f}%"


def _fmt_rate(bps: float | None) -> str:
    if bps is None:
        return "UNAVAILABLE"
    units = ["B/s", "KiB/s", "MiB/s", "GiB/s"]
    value = max(0.0, float(bps))
    unit = 0
    while value >= 1024 and unit < len(units) - 1:
        value /= 1024
        unit += 1
    return f"{value:.1f} {units[unit]}"


def print_summary(service: SystemMonitorService) -> None:
    snap = service.get_snapshot()
    print("System monitor ready.")
    print(f"CPU: {_fmt_pct(snap.cpu.usage_percent)}")
    print(f"Memory: {_fmt_pct(snap.memory.usage_percent)}")
    print(f"Disk read: {_fmt_rate(snap.disks.activity.read_bytes_per_second)}")
    print(f"Disk write: {_fmt_rate(snap.disks.activity.write_bytes_per_second)}")
    print(f"Network receive: {_fmt_rate(snap.network.receive_bytes_per_second)}")
    print(f"Network send: {_fmt_rate(snap.network.send_bytes_per_second)}")
    if snap.battery.present:
        print(f"Battery: {snap.battery.status.value} — {_fmt_pct(snap.battery.percent)}")
    else:
        print("Battery: No battery detected")
    print(f"GPU: {snap.gpu.reason or snap.gpu.availability.value}")
    print(f"Temperatures: {snap.temperatures.reason or snap.temperatures.availability.value}")


def print_capabilities(service: SystemMonitorService) -> None:
    caps = service.get_capabilities()
    if caps is None:
        print("Capabilities: DATA PENDING")
        return
    data = caps.model_dump(mode="json")
    for key, value in data.items():
        available = value.get("available")
        reason = value.get("reason") or ""
        code = value.get("code") or ""
        provider = value.get("provider") or ""
        limited = " (limited)" if value.get("limited") else ""
        detail = reason or (code if not available else "")
        bits = [f"{key}:", "available" if available else "unavailable"]
        if limited:
            bits.append(limited.strip())
        if provider:
            bits.append(f"[{provider}]")
        if detail:
            bits.append(f"— {detail}")
        print(" ".join(bits))


def print_processes(service: SystemMonitorService) -> None:
    procs = service.get_processes()
    print(
        f"Processes returned={procs.returned} observed={procs.total_observed} "
        f"limited={procs.limited_count}"
    )
    for proc in procs.processes[:25]:
        print(
            f"  {proc.pid:6d}  {(proc.name or '?'):24s}  "
            f"cpu={_fmt_pct(proc.cpu_percent):>10s}  "
            f"mem={_fmt_pct(proc.memory_percent):>10s}"
        )


def print_disks(service: SystemMonitorService) -> None:
    snap = service.get_snapshot()
    for drive in snap.disks.drives:
        print(
            f"{drive.mountpoint}  {drive.fstype or '?'}  "
            f"used={_fmt_pct(drive.usage_percent)}"
        )
    act = snap.disks.activity
    print(f"Aggregate read={_fmt_rate(act.read_bytes_per_second)} write={_fmt_rate(act.write_bytes_per_second)}")


def print_network(service: SystemMonitorService) -> None:
    snap = service.get_snapshot()
    print(
        f"Receive {_fmt_rate(snap.network.receive_bytes_per_second)}  "
        f"Send {_fmt_rate(snap.network.send_bytes_per_second)}"
    )
    for adapter in snap.network.adapters:
        state = "up" if adapter.is_up else "down"
        speed = f"{adapter.speed_mbps} Mbps" if adapter.speed_mbps is not None else "speed UNAVAILABLE"
        print(f"  {adapter.name}: {state} · {speed}")


def print_gpu(service: SystemMonitorService) -> None:
    gpu = service.get_snapshot().gpu
    print(f"Availability: {gpu.availability.value}")
    if gpu.reason:
        print(f"Reason: {gpu.reason}")
    for device in gpu.devices:
        print(
            f"  [{device.index}] {device.name} usage={_fmt_pct(device.usage_percent)} "
            f"temp={device.temperature_celsius if device.temperature_celsius is not None else 'UNAVAILABLE'}"
        )


def print_temperatures(service: SystemMonitorService) -> None:
    temps = service.get_snapshot().temperatures
    print(f"Availability: {temps.availability.value}")
    if temps.reason:
        print(f"Reason: {temps.reason}")
    for reading in temps.readings:
        print(f"  {reading.category}/{reading.name}: {reading.celsius:.1f}°C ({reading.provider})")


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    setup_logging(settings.log_level)
    service = SystemMonitorService(settings=settings, event_bus=None)
    await service.start()

    stop = asyncio.Event()

    def _sig(*_a: object) -> None:
        stop.set()

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_running_loop().add_signal_handler(sig, _sig)
            except NotImplementedError:
                signal.signal(sig, lambda *_: stop.set())
    except Exception:
        pass

    try:
        # Allow one fast sample so rates / CPU percentages become meaningful.
        await asyncio.sleep(1.2)
        if args.processes:
            # Ensure process table has finished (can be slower than fast metrics).
            await asyncio.sleep(2.0)
        await service.request_refresh()
        await asyncio.sleep(0.8)

        if args.capabilities:
            print_capabilities(service)
            return 0
        if args.processes:
            print_processes(service)
            return 0
        if args.disks:
            print_disks(service)
            return 0
        if args.network:
            print_network(service)
            return 0
        if args.gpu:
            print_gpu(service)
            return 0
        if args.temperatures:
            print_temperatures(service)
            return 0
        if args.watch:
            print_summary(service)
            deadline = asyncio.get_running_loop().time() + max(1.0, args.seconds)
            while not stop.is_set() and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(1.0)
                print("---")
                print_summary(service)
            return 0

        # Default: one snapshot
        print_summary(service)
        if args.snapshot or not any(
            [
                args.capabilities,
                args.watch,
                args.processes,
                args.disks,
                args.network,
                args.gpu,
                args.temperatures,
            ]
        ):
            snap = service.get_snapshot()
            print(f"Status: {snap.status.value} degraded={snap.degraded}")
            print(f"Hostname: {snap.static.hostname or 'HIDDEN'}")
            print(f"Uptime: {snap.static.uptime_seconds}s")
        return 0
    finally:
        await service.stop()


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
