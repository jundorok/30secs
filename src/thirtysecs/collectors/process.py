"""Process metrics collector."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
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


def get_process_detail(pid: int) -> dict[str, Any] | None:
    """Get detailed information about a specific process."""
    try:
        proc = psutil.Process(pid)

        # Basic info
        with proc.oneshot():
            info: dict[str, Any] = {
                "pid": proc.pid,
                "name": proc.name(),
                "status": proc.status(),
                "username": proc.username(),
                "cmdline": " ".join(proc.cmdline()) if proc.cmdline() else proc.name(),
                "cwd": None,
                "create_time": datetime.fromtimestamp(proc.create_time(), tz=UTC).isoformat(),
            }

            # Working directory (may fail due to permissions)
            with contextlib.suppress(psutil.AccessDenied, psutil.NoSuchProcess):
                info["cwd"] = proc.cwd()

            # CPU
            info["cpu"] = {
                "percent": round(proc.cpu_percent(interval=0.1), 2),
                "num_threads": proc.num_threads(),
            }

            # Memory detailed
            try:
                mem_info = proc.memory_info()
                info["memory"] = {
                    "rss": mem_info.rss,
                    "rss_human": _bytes_to_human(mem_info.rss),
                    "vms": mem_info.vms,
                    "vms_human": _bytes_to_human(mem_info.vms),
                    "percent": round(proc.memory_percent(), 2),
                }

                # memory_full_info may require elevated privileges
                try:
                    mem_full = proc.memory_full_info()
                    if hasattr(mem_full, "uss"):
                        info["memory"]["uss"] = mem_full.uss
                        info["memory"]["uss_human"] = _bytes_to_human(mem_full.uss)
                    if hasattr(mem_full, "pss"):
                        info["memory"]["pss"] = mem_full.pss
                        info["memory"]["pss_human"] = _bytes_to_human(mem_full.pss)
                except (psutil.AccessDenied, AttributeError):
                    pass  # memory_full_info not available, skip USS/PSS

            except (psutil.AccessDenied, psutil.NoSuchProcess):
                info["memory"] = {"error": "Access denied"}

            # Open files
            try:
                open_files = proc.open_files()
                info["open_files"] = {
                    "count": len(open_files),
                    "files": [f.path for f in open_files[:20]],  # Limit to 20
                }
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                info["open_files"] = {"count": 0, "error": "Access denied"}

            # Network connections
            try:
                connections = proc.net_connections()
                info["connections"] = {
                    "count": len(connections),
                    "details": [
                        {
                            "fd": c.fd,
                            "family": str(c.family),
                            "type": str(c.type),
                            "laddr": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else None,
                            "raddr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else None,
                            "status": c.status,
                        }
                        for c in connections[:20]  # Limit to 20
                    ],
                }
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                info["connections"] = {"count": 0, "error": "Access denied"}

            # Threads
            try:
                threads = proc.threads()
                info["threads"] = {
                    "count": len(threads),
                    "details": [
                        {"id": t.id, "user_time": t.user_time, "system_time": t.system_time}
                        for t in threads[:10]  # Limit to 10
                    ],
                }
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                info["threads"] = {"count": 0, "error": "Access denied"}

            # Environment variables (may be sensitive, limit output)
            try:
                environ = proc.environ()
                info["environ"] = {
                    "count": len(environ),
                    # Only show some common env vars
                    "selected": {
                        k: v
                        for k, v in environ.items()
                        if k in ("PATH", "HOME", "USER", "LANG", "JAVA_HOME", "NODE_ENV")
                    },
                }
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                info["environ"] = {"count": 0, "error": "Access denied"}

            # Parent process
            try:
                parent = proc.parent()
                if parent:
                    info["parent"] = {"pid": parent.pid, "name": parent.name()}
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass

            # Children processes
            try:
                children = proc.children(recursive=False)
                info["children"] = [{"pid": c.pid, "name": c.name()} for c in children[:10]]
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                info["children"] = []

        return info

    except psutil.NoSuchProcess:
        return None
    except psutil.AccessDenied:
        return {"pid": pid, "error": "Access denied"}


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
