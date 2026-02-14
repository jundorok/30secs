"""Network metrics collector."""

from __future__ import annotations

from typing import Any

import psutil

from .base import BaseCollector


def _bytes_to_human(n: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.2f} {unit}"
        n = int(n / 1024)
    return f"{n:.2f} PB"


class NetworkCollector(BaseCollector):
    """Collect network metrics."""

    @property
    def name(self) -> str:
        return "network"

    def collect(self) -> dict[str, Any]:
        # Network I/O counters
        net_io = psutil.net_io_counters()
        io_stats = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_sent_human": _bytes_to_human(net_io.bytes_sent),
            "bytes_recv": net_io.bytes_recv,
            "bytes_recv_human": _bytes_to_human(net_io.bytes_recv),
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "errin": net_io.errin,
            "errout": net_io.errout,
            "dropin": net_io.dropin,
            "dropout": net_io.dropout,
        }

        # Network interfaces
        interfaces = []
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        for iface_name, iface_addrs in addrs.items():
            iface_info: dict[str, Any] = {"name": iface_name, "addresses": []}

            # Get interface stats
            if iface_name in stats:
                s = stats[iface_name]
                iface_info["is_up"] = s.isup
                iface_info["speed"] = s.speed
                iface_info["mtu"] = s.mtu

            for addr in iface_addrs:
                addr_info = {
                    "family": str(addr.family.name),
                    "address": addr.address,
                }
                if addr.netmask:
                    addr_info["netmask"] = addr.netmask
                iface_info["addresses"].append(addr_info)

            interfaces.append(iface_info)

        # Connection counts by status
        connections: dict[str, int] = {}
        try:
            for conn in psutil.net_connections(kind="inet"):
                status = conn.status
                connections[status] = connections.get(status, 0) + 1
        except (psutil.AccessDenied, PermissionError):
            pass

        return {
            "io": io_stats,
            "interfaces": interfaces,
            "connections": connections,
        }
