"""System info collector."""

from __future__ import annotations

import platform
import socket
from datetime import UTC, datetime
from typing import Any

import psutil

from .base import BaseCollector


class SystemCollector(BaseCollector):
    """Collect system info."""

    @property
    def name(self) -> str:
        return "system"

    def collect(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=UTC)
        uptime_seconds = (now - boot_time).total_seconds()

        # Users logged in
        users = []
        try:
            for user in psutil.users():
                users.append(
                    {
                        "name": user.name,
                        "terminal": user.terminal,
                        "host": user.host,
                        "started": datetime.fromtimestamp(user.started, tz=UTC).isoformat(),
                    }
                )
        except Exception:
            pass

        return {
            "hostname": socket.gethostname(),
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
            },
            "boot_time": boot_time.isoformat(timespec="seconds"),
            "uptime_seconds": round(uptime_seconds, 0),
            "uptime_human": _format_uptime(uptime_seconds),
            "users": users,
        }


def _format_uptime(seconds: float) -> str:
    """Format uptime in human-readable format."""
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)
