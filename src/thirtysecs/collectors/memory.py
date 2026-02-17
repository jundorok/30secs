"""Memory metrics collector."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import psutil

from .base import BaseCollector

log = logging.getLogger(__name__)


def _bytes_to_human(n: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.2f} {unit}"
        n = int(n / 1024)
    return f"{n:.2f} PB"


# ── cgroup helpers ────────────────────────────────────────────────────


def _read_int(path: Path) -> int | None:
    """Read an integer from a cgroup pseudo-file, return None on failure."""
    try:
        text = path.read_text().strip()
        if text in ("max", "9223372036854771712"):
            return None  # unlimited
        return int(text)
    except (OSError, ValueError):
        return None


def _read_cgroup_v2_memory() -> dict[str, Any] | None:
    """Read cgroup v2 memory stats (unified hierarchy)."""
    # Find the cgroup path for this process
    cgroup_file = Path("/proc/self/cgroup")
    if not cgroup_file.exists():
        return None

    try:
        cgroup_line = cgroup_file.read_text().strip()
    except OSError:
        return None

    # cgroup v2 format: "0::/path"
    cgroup_path: str | None = None
    for line in cgroup_line.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3 and parts[0] == "0":
            cgroup_path = parts[2]
            break

    if cgroup_path is None:
        return None

    base = Path("/sys/fs/cgroup") / cgroup_path.lstrip("/")
    if not base.exists():
        return None

    result: dict[str, Any] = {}
    limit = _read_int(base / "memory.max")
    if limit is not None:
        result["limit"] = limit
        result["limit_human"] = _bytes_to_human(limit)
    current = _read_int(base / "memory.current")
    if current is not None:
        result["usage"] = current
        result["usage_human"] = _bytes_to_human(current)
        if limit is not None and limit > 0:
            result["percent"] = round(current / limit * 100, 2)

    swap_max = _read_int(base / "memory.swap.max")
    swap_cur = _read_int(base / "memory.swap.current")
    if swap_cur is not None:
        result["swap_usage"] = swap_cur
        if swap_max is not None and swap_max > 0:
            result["swap_percent"] = round(swap_cur / swap_max * 100, 2)

    # memory.pressure (PSI) – format: "some avg10=0.00 avg60=0.00 avg300=0.00 total=0"
    pressure_path = base / "memory.pressure"
    if pressure_path.exists():
        result["pressure"] = _parse_psi(pressure_path)

    return result or None


def _read_cgroup_v1_memory() -> dict[str, Any] | None:
    """Read cgroup v1 memory stats."""
    base = Path("/sys/fs/cgroup/memory")
    if not base.exists():
        return None

    result: dict[str, Any] = {}
    limit = _read_int(base / "memory.limit_in_bytes")
    usage = _read_int(base / "memory.usage_in_bytes")
    if limit is not None:
        result["limit"] = limit
        result["limit_human"] = _bytes_to_human(limit)
    if usage is not None:
        result["usage"] = usage
        result["usage_human"] = _bytes_to_human(usage)
        if limit is not None and limit > 0:
            result["percent"] = round(usage / limit * 100, 2)

    return result or None


def _parse_psi(path: Path) -> dict[str, Any]:
    """Parse a PSI (Pressure Stall Information) file."""
    psi: dict[str, Any] = {}
    try:
        for line in path.read_text().strip().splitlines():
            parts = line.split()
            if not parts:
                continue
            kind = parts[0]  # "some" or "full"
            metrics: dict[str, float] = {}
            for token in parts[1:]:
                if "=" in token:
                    key, val = token.split("=", 1)
                    try:
                        metrics[key] = float(val)
                    except ValueError:
                        pass
            if metrics:
                psi[kind] = metrics
    except OSError:
        pass
    return psi


def collect_cgroup_memory() -> dict[str, Any] | None:
    """Return cgroup memory info (v2 first, fallback to v1)."""
    info = _read_cgroup_v2_memory()
    if info is not None:
        info["version"] = 2
        return info
    info = _read_cgroup_v1_memory()
    if info is not None:
        info["version"] = 1
        return info
    return None


# ── System-wide PSI ──────────────────────────────────────────────────


def collect_system_psi() -> dict[str, Any] | None:
    """Read system-wide memory pressure from /proc/pressure/memory."""
    path = Path("/proc/pressure/memory")
    if not path.exists():
        return None
    result = _parse_psi(path)
    return result or None


# ── /proc/meminfo extras ─────────────────────────────────────────────


def collect_meminfo_details() -> dict[str, Any]:
    """Parse extra fields from /proc/meminfo not exposed by psutil."""
    fields_of_interest = {
        "Buffers", "Cached", "Slab", "SReclaimable", "SUnreclaim",
        "PageTables", "KernelStack", "Mapped", "Shmem",
        "CommitLimit", "Committed_AS", "HugePages_Total",
        "HugePages_Free", "Hugepagesize", "DirectMap4k",
        "DirectMap2M", "DirectMap1G",
    }
    result: dict[str, Any] = {}
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                parts = line.split(":")
                if len(parts) != 2:
                    continue
                key = parts[0].strip()
                if key not in fields_of_interest:
                    continue
                val_parts = parts[1].strip().split()
                try:
                    value_kb = int(val_parts[0])
                except (ValueError, IndexError):
                    continue
                # /proc/meminfo reports in kB
                value_bytes = value_kb * 1024
                result[key] = value_bytes
                result[f"{key}_human"] = _bytes_to_human(value_bytes)
    except OSError:
        pass
    return result


class MemoryCollector(BaseCollector):
    """Collect memory metrics."""

    @property
    def name(self) -> str:
        return "memory"

    def collect(self) -> dict[str, Any]:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()

        data: dict[str, Any] = {
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

        # cgroup memory limits (Kubernetes / container-aware)
        cgroup = collect_cgroup_memory()
        if cgroup is not None:
            data["cgroup"] = cgroup

        # Extra /proc/meminfo details
        meminfo = collect_meminfo_details()
        if meminfo:
            data["detail"] = meminfo

        # System-wide memory pressure (PSI)
        psi = collect_system_psi()
        if psi is not None:
            data["pressure"] = psi

        return data
