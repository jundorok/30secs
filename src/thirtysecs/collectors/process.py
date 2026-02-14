"""Process metrics collector."""

from __future__ import annotations

from typing import Any

import psutil

from .base import BaseCollector


class ProcessCollector(BaseCollector):
    """Collect process metrics."""

    def __init__(self, top_n: int = 10) -> None:
        self.top_n = top_n

    @property
    def name(self) -> str:
        return "processes"

    def collect(self) -> dict[str, Any]:
        processes: list[dict[str, Any]] = []

        for proc in psutil.process_iter(
            ["pid", "name", "username", "cpu_percent", "memory_percent", "status"]
        ):
            try:
                info = proc.info
                processes.append(
                    {
                        "pid": info["pid"],
                        "name": info["name"],
                        "username": info["username"],
                        "cpu_percent": round(info["cpu_percent"] or 0, 2),
                        "memory_percent": round(info["memory_percent"] or 0, 2),
                        "status": info["status"],
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by CPU usage and get top N
        top_by_cpu = sorted(processes, key=lambda x: x["cpu_percent"], reverse=True)[: self.top_n]
        top_by_memory = sorted(processes, key=lambda x: x["memory_percent"], reverse=True)[
            : self.top_n
        ]

        # Process status counts
        status_counts: dict[str, int] = {}
        for p in processes:
            status = p["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total": len(processes),
            "status_counts": status_counts,
            "top_by_cpu": top_by_cpu,
            "top_by_memory": top_by_memory,
        }
