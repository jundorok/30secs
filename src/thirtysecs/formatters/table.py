"""Table formatter for human-readable output."""

from __future__ import annotations

from typing import Any

from .base import BaseFormatter


class TableFormatter(BaseFormatter):
    """Format snapshot as human-readable table."""

    def format(self, snapshot: dict[str, Any]) -> str:
        lines: list[str] = []

        # Header
        ts = snapshot.get("timestamp", "")
        lines.append(f"{'=' * 60}")
        lines.append(f"  System Snapshot - {ts}")
        lines.append(f"{'=' * 60}")

        # System info
        if "system" in snapshot:
            sys_info = snapshot["system"]
            lines.append("")
            lines.append("📌 SYSTEM")
            lines.append(f"  Hostname:  {sys_info.get('hostname', 'N/A')}")
            platform = sys_info.get("platform", {})
            lines.append(f"  OS:        {platform.get('system', '')} {platform.get('release', '')}")
            lines.append(f"  Uptime:    {sys_info.get('uptime_human', 'N/A')}")

        # CPU
        if "cpu" in snapshot:
            cpu = snapshot["cpu"]
            lines.append("")
            lines.append("🖥  CPU")
            lines.append(f"  Usage:     {cpu.get('percent', 0):.1f}%")
            lines.append(
                f"  Cores:     {cpu.get('count_physical', 0)} physical / {cpu.get('count_logical', 0)} logical"
            )
            loadavg = cpu.get("loadavg")
            if loadavg:
                lines.append(
                    f"  Load Avg:  {loadavg.get('1m', 0):.2f} / {loadavg.get('5m', 0):.2f} / {loadavg.get('15m', 0):.2f}"
                )

        # Memory
        if "memory" in snapshot:
            mem = snapshot["memory"]
            vm = mem.get("virtual", {})
            lines.append("")
            lines.append("💾 MEMORY")
            lines.append(
                f"  Used:      {vm.get('used_human', 'N/A')} / {vm.get('total_human', 'N/A')} ({vm.get('percent', 0):.1f}%)"
            )
            lines.append(f"  Available: {vm.get('available_human', 'N/A')}")

            swap = mem.get("swap", {})
            if swap.get("total", 0) > 0:
                lines.append(
                    f"  Swap:      {swap.get('used_human', 'N/A')} / {swap.get('total_human', 'N/A')} ({swap.get('percent', 0):.1f}%)"
                )

        # Disk
        if "disk" in snapshot:
            disk = snapshot["disk"]
            partitions = disk.get("partitions", [])
            if partitions:
                lines.append("")
                lines.append("💿 DISK")
                for p in partitions[:5]:  # Limit to 5 partitions
                    lines.append(
                        f"  {p.get('mountpoint', 'N/A'):15} {p.get('used_human', 'N/A'):>10} / {p.get('total_human', 'N/A'):>10} ({p.get('percent', 0):.1f}%)"
                    )

        # Network
        if "network" in snapshot:
            net = snapshot["network"]
            io = net.get("io", {})
            lines.append("")
            lines.append("🌐 NETWORK")
            lines.append(f"  Sent:      {io.get('bytes_sent_human', 'N/A')}")
            lines.append(f"  Received:  {io.get('bytes_recv_human', 'N/A')}")

            conns = net.get("connections", {})
            if conns:
                conn_str = ", ".join(f"{k}: {v}" for k, v in sorted(conns.items()))
                lines.append(f"  Conns:     {conn_str}")

        # Processes
        if "processes" in snapshot:
            procs = snapshot["processes"]
            lines.append("")
            lines.append("⚙️  PROCESSES")
            lines.append(f"  Total:     {procs.get('total', 0)}")

            top_cpu = procs.get("top_by_cpu", [])[:5]
            if top_cpu:
                lines.append("  Top by CPU:")
                for p in top_cpu:
                    lines.append(
                        f"    {p.get('pid', 0):>6}  {p.get('name', 'N/A')[:20]:20} CPU: {p.get('cpu_percent', 0):>5.1f}%  MEM: {p.get('memory_percent', 0):>5.1f}%"
                    )

        lines.append("")
        lines.append(f"{'=' * 60}")

        return "\n".join(lines)
