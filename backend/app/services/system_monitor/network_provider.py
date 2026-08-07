"""Network throughput and adapter inventory."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from app.models.system_metrics import (
    AvailabilityReason,
    NetworkAdapterMetrics,
    NetworkMetrics,
)
from app.services.system_monitor.metric_rate_calculator import MetricRateCalculator


class NetworkBackend(Protocol):
    def net_io_counters(self, pernic: bool = False) -> object: ...

    def net_if_stats(self) -> dict[str, object]: ...

    def net_if_addrs(self) -> dict[str, list[object]]: ...


class PsutilNetworkBackend:
    def net_io_counters(self, pernic: bool = False) -> object:
        import psutil

        return psutil.net_io_counters(pernic=pernic)

    def net_if_stats(self) -> dict[str, object]:
        import psutil

        return dict(psutil.net_if_stats())

    def net_if_addrs(self) -> dict[str, list[object]]:
        import psutil

        return dict(psutil.net_if_addrs())


_VIRTUAL_HINTS = ("vethernet", "hyper-v", "virtualbox", "vmware", "docker", "wsl")


class NetworkProvider:
    def __init__(
        self,
        backend: NetworkBackend | None = None,
        rates: MetricRateCalculator | None = None,
        *,
        include_loopback: bool = False,
        include_disconnected: bool = False,
        include_virtual: bool = True,
        show_ip: bool = False,
    ) -> None:
        self._backend = backend or PsutilNetworkBackend()
        self._rates = rates or MetricRateCalculator()
        self._include_loopback = include_loopback
        self._include_disconnected = include_disconnected
        self._include_virtual = include_virtual
        self._show_ip = show_ip

    def _is_loopback(self, name: str) -> bool:
        lowered = name.lower()
        return lowered.startswith("lo") or "loopback" in lowered

    def _is_virtual(self, name: str) -> bool:
        lowered = name.lower()
        return any(hint in lowered for hint in _VIRTUAL_HINTS)

    def collect(self) -> NetworkMetrics:
        now = datetime.now(timezone.utc)
        try:
            total = self._backend.net_io_counters(pernic=False)
            recv_total = int(getattr(total, "bytes_recv", 0) or 0)
            sent_total = int(getattr(total, "bytes_sent", 0) or 0)
            recv_rate = self._rates.rate("net.recv", float(recv_total))
            send_rate = self._rates.rate("net.sent", float(sent_total))
        except Exception:
            return NetworkMetrics(
                collected_at=now,
                availability=AvailabilityReason.UNAVAILABLE,
            )

        adapters: list[NetworkAdapterMetrics] = []
        active = 0
        try:
            stats = self._backend.net_if_stats()
            addrs = self._backend.net_if_addrs() if self._show_ip else {}
            for name, stat in stats.items():
                if not self._include_loopback and self._is_loopback(name):
                    continue
                if not self._include_virtual and self._is_virtual(name):
                    continue
                is_up = bool(getattr(stat, "isup", False))
                if not self._include_disconnected and not is_up:
                    continue
                ipv4 = None
                has_ipv6 = None
                if self._show_ip:
                    has_ipv6 = False
                    for addr in addrs.get(name, []):
                        family = str(getattr(addr, "family", ""))
                        address = str(getattr(addr, "address", "") or "")
                        if "AF_INET6" in family or family.endswith("23"):
                            has_ipv6 = True
                        elif ("AF_INET" in family or family.endswith("2")) and ipv4 is None:
                            if address and not address.startswith("127."):
                                ipv4 = address
                if is_up:
                    active += 1
                adapters.append(
                    NetworkAdapterMetrics(
                        name=name,
                        is_up=is_up,
                        speed_mbps=float(getattr(stat, "speed", 0) or 0) or None,
                        mtu=int(getattr(stat, "mtu", 0) or 0) or None,
                        ipv4=ipv4,
                        has_ipv6=has_ipv6,
                    )
                )
        except Exception:
            adapters = []

        availability = AvailabilityReason.AVAILABLE
        if not recv_rate.available and not send_rate.available:
            availability = AvailabilityReason.DATA_PENDING

        return NetworkMetrics(
            receive_bytes_per_second=recv_rate.value if recv_rate.available else None,
            send_bytes_per_second=send_rate.value if send_rate.available else None,
            bytes_recv_total=recv_total,
            bytes_sent_total=sent_total,
            adapters=adapters,
            active_adapter_count=active,
            collected_at=now,
            availability=availability,
        )
