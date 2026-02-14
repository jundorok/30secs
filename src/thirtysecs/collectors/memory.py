"""Memory metrics collector."""

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


class MemoryCollector(BaseCollector):
    """Collect memory metrics."""

    @property
    def name(self) -> str:
        return "memory"

    def collect(self) -> dict[str, Any]:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return {
            "virtual": {
                "total": vm.total,
                "total_human": _bytes_to_human(vm.total),
                "available": vm.available,
                "available_human": _bytes_to_human(vm.available),
                "used": vm.used,
                "used_human": _bytes_to_human(vm.used),
                "free": vm.free,
                "percent": round(vm.percent, 2),
            },
            "swap": {
                "total": swap.total,
                "total_human": _bytes_to_human(swap.total),
                "used": swap.used,
                "used_human": _bytes_to_human(swap.used),
                "free": swap.free,
                "percent": round(swap.percent, 2),
            },
        }
