"""Prometheus metrics formatter."""

from __future__ import annotations

from typing import Any

from .base import BaseFormatter


class PrometheusFormatter(BaseFormatter):
    """Format snapshot as Prometheus metrics."""

    def format(self, snapshot: dict[str, Any]) -> str:
        lines: list[str] = []
        hostname = snapshot.get("system", {}).get("hostname", "unknown")

        # CPU metrics
        if "cpu" in snapshot:
            cpu = snapshot["cpu"]
            lines.append("# HELP thirtysecs_cpu_percent CPU usage percentage")
            lines.append("# TYPE thirtysecs_cpu_percent gauge")
            lines.append(f'thirtysecs_cpu_percent{{host="{hostname}"}} {cpu.get("percent", 0)}')

            lines.append("# HELP thirtysecs_cpu_count_logical Number of logical CPUs")
            lines.append("# TYPE thirtysecs_cpu_count_logical gauge")
            lines.append(
                f'thirtysecs_cpu_count_logical{{host="{hostname}"}} {cpu.get("count_logical", 0)}'
            )

            loadavg = cpu.get("loadavg")
            if loadavg:
                lines.append("# HELP thirtysecs_load_1m 1 minute load average")
                lines.append("# TYPE thirtysecs_load_1m gauge")
                lines.append(f'thirtysecs_load_1m{{host="{hostname}"}} {loadavg.get("1m", 0)}')

                lines.append("# HELP thirtysecs_load_5m 5 minute load average")
                lines.append("# TYPE thirtysecs_load_5m gauge")
                lines.append(f'thirtysecs_load_5m{{host="{hostname}"}} {loadavg.get("5m", 0)}')

                lines.append("# HELP thirtysecs_load_15m 15 minute load average")
                lines.append("# TYPE thirtysecs_load_15m gauge")
                lines.append(f'thirtysecs_load_15m{{host="{hostname}"}} {loadavg.get("15m", 0)}')

        # Memory metrics
        if "memory" in snapshot:
            mem = snapshot["memory"]
            vm = mem.get("virtual", {})

            lines.append("# HELP thirtysecs_memory_total_bytes Total memory in bytes")
            lines.append("# TYPE thirtysecs_memory_total_bytes gauge")
            lines.append(f'thirtysecs_memory_total_bytes{{host="{hostname}"}} {vm.get("total", 0)}')

            lines.append("# HELP thirtysecs_memory_used_bytes Used memory in bytes")
            lines.append("# TYPE thirtysecs_memory_used_bytes gauge")
            lines.append(f'thirtysecs_memory_used_bytes{{host="{hostname}"}} {vm.get("used", 0)}')

            lines.append("# HELP thirtysecs_memory_available_bytes Available memory in bytes")
            lines.append("# TYPE thirtysecs_memory_available_bytes gauge")
            lines.append(
                f'thirtysecs_memory_available_bytes{{host="{hostname}"}} {vm.get("available", 0)}'
            )

            lines.append("# HELP thirtysecs_memory_percent Memory usage percentage")
            lines.append("# TYPE thirtysecs_memory_percent gauge")
            lines.append(f'thirtysecs_memory_percent{{host="{hostname}"}} {vm.get("percent", 0)}')

        # Disk metrics
        if "disk" in snapshot:
            disk = snapshot["disk"]
            partitions = disk.get("partitions", [])

            if partitions:
                lines.append("# HELP thirtysecs_disk_total_bytes Total disk space in bytes")
                lines.append("# TYPE thirtysecs_disk_total_bytes gauge")

                for p in partitions:
                    mp = p.get("mountpoint", "unknown").replace('"', '\\"')
                    lines.append(
                        f'thirtysecs_disk_total_bytes{{host="{hostname}",mountpoint="{mp}"}} {p.get("total", 0)}'
                    )

                lines.append("# HELP thirtysecs_disk_used_bytes Used disk space in bytes")
                lines.append("# TYPE thirtysecs_disk_used_bytes gauge")

                for p in partitions:
                    mp = p.get("mountpoint", "unknown").replace('"', '\\"')
                    lines.append(
                        f'thirtysecs_disk_used_bytes{{host="{hostname}",mountpoint="{mp}"}} {p.get("used", 0)}'
                    )

                lines.append("# HELP thirtysecs_disk_percent Disk usage percentage")
                lines.append("# TYPE thirtysecs_disk_percent gauge")

                for p in partitions:
                    mp = p.get("mountpoint", "unknown").replace('"', '\\"')
                    lines.append(
                        f'thirtysecs_disk_percent{{host="{hostname}",mountpoint="{mp}"}} {p.get("percent", 0)}'
                    )

        # Network metrics
        if "network" in snapshot:
            net = snapshot["network"]
            io = net.get("io", {})

            lines.append("# HELP thirtysecs_network_bytes_sent_total Total bytes sent")
            lines.append("# TYPE thirtysecs_network_bytes_sent_total counter")
            lines.append(
                f'thirtysecs_network_bytes_sent_total{{host="{hostname}"}} {io.get("bytes_sent", 0)}'
            )

            lines.append("# HELP thirtysecs_network_bytes_recv_total Total bytes received")
            lines.append("# TYPE thirtysecs_network_bytes_recv_total counter")
            lines.append(
                f'thirtysecs_network_bytes_recv_total{{host="{hostname}"}} {io.get("bytes_recv", 0)}'
            )

        # Process metrics
        if "processes" in snapshot:
            procs = snapshot["processes"]

            lines.append("# HELP thirtysecs_processes_total Total number of processes")
            lines.append("# TYPE thirtysecs_processes_total gauge")
            lines.append(f'thirtysecs_processes_total{{host="{hostname}"}} {procs.get("total", 0)}')

        return "\n".join(lines)
