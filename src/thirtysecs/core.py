"""Core snapshot collection logic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .collectors import (
    CPUCollector,
    DiskCollector,
    MemoryCollector,
    NetworkCollector,
    ProcessCollector,
    SystemCollector,
)
from .collectors.base import BaseCollector


def collect_snapshot(
    *,
    include_processes: bool = True,
    include_network: bool = True,
    include_disk: bool = True,
) -> dict[str, Any]:
    """Collect a complete system snapshot.

    Args:
        include_processes: Include process information (may be slower)
        include_network: Include network information
        include_disk: Include disk information

    Returns:
        Dictionary containing all collected metrics
    """
    collectors: list[BaseCollector] = [
        SystemCollector(),
        CPUCollector(),
        MemoryCollector(),
    ]

    if include_disk:
        collectors.append(DiskCollector())

    if include_network:
        collectors.append(NetworkCollector())

    if include_processes:
        collectors.append(ProcessCollector())

    snapshot: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
    }

    for collector in collectors:
        try:
            snapshot[collector.name] = collector.collect()
        except Exception as e:
            snapshot[collector.name] = {"error": str(e)}

    return snapshot


def collect_quick_snapshot() -> dict[str, Any]:
    """Collect a quick snapshot without processes (faster)."""
    return collect_snapshot(include_processes=False)
