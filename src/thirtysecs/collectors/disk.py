"""Disk metrics collector."""

from __future__ import annotations

from typing import Any

import psutil

from ..utils import bytes_to_human
from .base import BaseCollector


class DiskCollector(BaseCollector):
    """Collect disk metrics."""

    @property
    def name(self) -> str:
        return "disk"

    def collect(self) -> dict[str, Any]:
        partitions = []

        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append(
                    {
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total": usage.total,
                        "total_human": bytes_to_human(usage.total),
                        "used": usage.used,
                        "used_human": bytes_to_human(usage.used),
                        "free": usage.free,
                        "free_human": bytes_to_human(usage.free),
                        "percent": round(usage.percent, 2),
                    }
                )
            except (PermissionError, OSError):
                continue

        # Disk I/O stats
        io_counters = None
        try:
            io = psutil.disk_io_counters()
            if io:
                io_counters = {
                    "read_count": io.read_count,
                    "write_count": io.write_count,
                    "read_bytes": io.read_bytes,
                    "read_bytes_human": bytes_to_human(io.read_bytes),
                    "write_bytes": io.write_bytes,
                    "write_bytes_human": bytes_to_human(io.write_bytes),
                }
        except Exception:
            pass

        return {
            "partitions": partitions,
            "io": io_counters,
        }
