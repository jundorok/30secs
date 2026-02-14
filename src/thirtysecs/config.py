from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get_str(name: str, default: str) -> str:
    return os.getenv(name, default)


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


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw not in {"0", "false", "False"}


@dataclass(frozen=True, slots=True)
class Settings:
    service_name: str = field(default_factory=lambda: _get_str("SERVICE_NAME", "30secs"))
    default_interval_seconds: int = field(
        default_factory=lambda: _get_int("DEFAULT_INTERVAL_SECONDS", 30)
    )
    include_hostname: bool = field(default_factory=lambda: _get_bool("INCLUDE_HOSTNAME", True))

    # Alert thresholds (configurable via environment variables)
    alert_cpu_threshold: float = field(
        default_factory=lambda: _get_float("ALERT_CPU_THRESHOLD", 90.0)
    )
    alert_memory_threshold: float = field(
        default_factory=lambda: _get_float("ALERT_MEMORY_THRESHOLD", 90.0)
    )
    alert_memory_critical_threshold: float = field(
        default_factory=lambda: _get_float("ALERT_MEMORY_CRITICAL_THRESHOLD", 95.0)
    )
    alert_swap_threshold: float = field(
        default_factory=lambda: _get_float("ALERT_SWAP_THRESHOLD", 80.0)
    )

    # Memory leak detection settings
    memory_leak_window_size: int = field(
        default_factory=lambda: _get_int("MEMORY_LEAK_WINDOW_SIZE", 10)
    )
    memory_leak_growth_threshold: float = field(
        default_factory=lambda: _get_float("MEMORY_LEAK_GROWTH_THRESHOLD", 5.0)
    )


settings = Settings()
