from __future__ import annotations

import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "30secs")
    default_interval_seconds: int = _get_int("DEFAULT_INTERVAL_SECONDS", 30)
    include_hostname: bool = os.getenv("INCLUDE_HOSTNAME", "1") not in {"0", "false", "False"}

    # Alert thresholds (configurable via environment variables)
    alert_cpu_threshold: float = _get_float("ALERT_CPU_THRESHOLD", 90.0)
    alert_memory_threshold: float = _get_float("ALERT_MEMORY_THRESHOLD", 90.0)
    alert_memory_critical_threshold: float = _get_float("ALERT_MEMORY_CRITICAL_THRESHOLD", 95.0)
    alert_swap_threshold: float = _get_float("ALERT_SWAP_THRESHOLD", 80.0)

    # Memory leak detection settings
    memory_leak_window_size: int = _get_int("MEMORY_LEAK_WINDOW_SIZE", 10)  # samples to track
    memory_leak_growth_threshold: float = _get_float("MEMORY_LEAK_GROWTH_THRESHOLD", 5.0)  # % growth over window


settings = Settings()
