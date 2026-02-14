from __future__ import annotations

import os
import platform
import socket
from datetime import datetime, timezone
from typing import Any

from .config import settings
from .errors import AppError


def _safe_getloadavg() -> tuple[float, float, float] | None:
    try:
        return os.getloadavg()
    except (AttributeError, OSError):
        return None


def collect_snapshot() -> dict[str, Any]:
    """Collect a lightweight system snapshot.

    Designed to be:
    - fast
    - safe to call in Lambda/container environments
    - robust across OSs (best-effort fields)
    """
    try:
        import psutil  # type: ignore
    except Exception as e:  # pragma: no cover
        raise AppError(
            status_code=500,
            code="dependency_missing",
            message="psutil is required but could not be imported.",
        ) from e

    now = datetime.now(timezone.utc)
    boot_ts = psutil.boot_time()
    uptime_seconds = max(0.0, now.timestamp() - float(boot_ts))

    # cpu_percent: first call can be 0.0; interval=0.0 returns last computed.
    # We use a small non-zero interval for a stable value.
    cpu_percent = float(psutil.cpu_percent(interval=0.05))

    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()

    # Disk: root mount best-effort
    try:
        disk_root = psutil.disk_usage(os.sep)
        disk = {
            "path": os.sep,
            "total": int(disk_root.total),
            "used": int(disk_root.used),
            "free": int(disk_root.free),
            "percent": float(disk_root.percent),
        }
    except Exception:
        disk = None

    loadavg = _safe_getloadavg()
    load = None if loadavg is None else {"1m": loadavg[0], "5m": loadavg[1], "15m": loadavg[2]}

    snapshot: dict[str, Any] = {
        "ts": now.isoformat(timespec="seconds"),
        "uptime_seconds": round(uptime_seconds, 3),
        "cpu": {"percent": round(cpu_percent, 2), "count": int(psutil.cpu_count() or 0)},
        "memory": {
            "total": int(vm.total),
            "available": int(vm.available),
            "used": int(vm.used),
            "free": int(getattr(vm, "free", 0)),
            "percent": float(vm.percent),
        },
        "swap": {"total": int(sm.total), "used": int(sm.used), "free": int(sm.free), "percent": float(sm.percent)},
        "disk_root": disk,
        "loadavg": load,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
    }

    if settings.include_hostname:
        snapshot["host"] = {"hostname": socket.gethostname()}

    return snapshot
