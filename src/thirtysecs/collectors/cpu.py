"""CPU metrics collector."""

from __future__ import annotations

import os
from typing import Any

import psutil

from .base import BaseCollector


class CPUCollector(BaseCollector):
    """Collect CPU metrics."""

    @property
    def name(self) -> str:
        return "cpu"

    def collect(self) -> dict[str, Any]:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_percent_per_core = psutil.cpu_percent(interval=0, percpu=True)
        cpu_count_logical = psutil.cpu_count(logical=True) or 0
        cpu_count_physical = psutil.cpu_count(logical=False) or 0

        # CPU frequency
        freq = psutil.cpu_freq()
        freq_info = None
        if freq:
            freq_info = {
                "current": round(freq.current, 2),
                "min": round(freq.min, 2),
                "max": round(freq.max, 2),
            }

        # Load average (Unix only)
        loadavg = None
        try:
            load = os.getloadavg()
            loadavg = {
                "1m": round(load[0], 2),
                "5m": round(load[1], 2),
                "15m": round(load[2], 2),
            }
        except (AttributeError, OSError):
            pass

        # CPU times
        cpu_times = psutil.cpu_times()
        times = {
            "user": round(cpu_times.user, 2),
            "system": round(cpu_times.system, 2),
            "idle": round(cpu_times.idle, 2),
        }

        return {
            "percent": round(cpu_percent, 2),
            "percent_per_core": [round(p, 2) for p in cpu_percent_per_core],
            "count_logical": cpu_count_logical,
            "count_physical": cpu_count_physical,
            "frequency": freq_info,
            "loadavg": loadavg,
            "times": times,
        }
