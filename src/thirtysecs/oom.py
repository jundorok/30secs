"""OOM (Out-Of-Memory) killer event detection and analysis.

Parses kernel OOM events from dmesg and systemd journal to surface
recent kills with process details and memory state at time of kill.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# Matches kernel OOM lines like:
#   "Out of memory: Killed process 12345 (myapp) total-vm:123456kB ..."
_OOM_KILLED_RE = re.compile(
    r"Out of memory: Killed process\s+(?P<pid>\d+)\s+"
    r"\((?P<name>[^)]+)\)\s+"
    r"total-vm:(?P<total_vm>\d+)kB,\s*"
    r"anon-rss:(?P<anon_rss>\d+)kB,\s*"
    r"file-rss:(?P<file_rss>\d+)kB",
)

# Simpler fallback for abbreviated lines
_OOM_KILLED_SHORT_RE = re.compile(
    r"Killed process\s+(?P<pid>\d+)\s+\((?P<name>[^)]+)\)",
)

# Matches the "oom-kill:" summary line (kernel ≥ 4.18)
_OOM_SUMMARY_RE = re.compile(
    r"oom-kill:.*task_memcg=(?P<memcg>\S+).*task=(?P<task>\S+)\s+pid=(?P<pid>\d+)",
)


@dataclass
class OomEvent:
    """A single OOM kill event."""

    pid: int
    name: str
    total_vm_kb: int | None = None
    anon_rss_kb: int | None = None
    file_rss_kb: int | None = None
    memcg: str | None = None
    raw_line: str = ""
    source: str = ""  # "dmesg" or "journal"


@dataclass
class OomReport:
    """Aggregated OOM report."""

    events: list[OomEvent] = field(default_factory=list)
    total_events: int = 0
    most_killed_process: str | None = None
    source_errors: list[str] = field(default_factory=list)


def _parse_oom_events(lines: list[str], source: str) -> list[OomEvent]:
    """Extract OOM events from log lines."""
    events: list[OomEvent] = []
    for line in lines:
        m = _OOM_KILLED_RE.search(line)
        if m:
            events.append(
                OomEvent(
                    pid=int(m.group("pid")),
                    name=m.group("name"),
                    total_vm_kb=int(m.group("total_vm")),
                    anon_rss_kb=int(m.group("anon_rss")),
                    file_rss_kb=int(m.group("file_rss")),
                    raw_line=line.strip(),
                    source=source,
                )
            )
            continue
        # Try summary format
        m = _OOM_SUMMARY_RE.search(line)
        if m:
            events.append(
                OomEvent(
                    pid=int(m.group("pid")),
                    name=m.group("task"),
                    memcg=m.group("memcg"),
                    raw_line=line.strip(),
                    source=source,
                )
            )
            continue
        # Fallback short format
        m = _OOM_KILLED_SHORT_RE.search(line)
        if m:
            events.append(
                OomEvent(
                    pid=int(m.group("pid")),
                    name=m.group("name"),
                    raw_line=line.strip(),
                    source=source,
                )
            )
    return events


def _read_dmesg() -> tuple[list[str], str | None]:
    """Read dmesg output, return (lines, error_message)."""
    try:
        result = subprocess.run(
            ["dmesg", "--time-format=iso", "-l", "err,crit,alert,emerg"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            # Fallback without time format (older kernels)
            result = subprocess.run(
                ["dmesg"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        return result.stdout.splitlines(), None
    except FileNotFoundError:
        return [], "dmesg command not found"
    except subprocess.TimeoutExpired:
        return [], "dmesg timed out"
    except OSError as exc:
        return [], f"dmesg error: {exc}"


def _read_journal() -> tuple[list[str], str | None]:
    """Read OOM events from systemd journal."""
    try:
        result = subprocess.run(
            [
                "journalctl",
                "-k",  # kernel messages
                "--no-pager",
                "-p", "err",  # error priority and above
                "-n", "500",  # last 500 entries
                "--output=short-iso",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return [], f"journalctl exited with code {result.returncode}"
        return result.stdout.splitlines(), None
    except FileNotFoundError:
        return [], "journalctl not available"
    except subprocess.TimeoutExpired:
        return [], "journalctl timed out"
    except OSError as exc:
        return [], f"journalctl error: {exc}"


def collect_oom_events() -> OomReport:
    """Collect recent OOM kill events from dmesg and journal."""
    report = OomReport()

    dmesg_lines, dmesg_err = _read_dmesg()
    if dmesg_err:
        report.source_errors.append(dmesg_err)
    dmesg_events = _parse_oom_events(dmesg_lines, source="dmesg")

    journal_lines, journal_err = _read_journal()
    if journal_err:
        report.source_errors.append(journal_err)
    journal_events = _parse_oom_events(journal_lines, source="journal")

    # Deduplicate by (pid, name) keeping the richest record
    seen: dict[tuple[int, str], OomEvent] = {}
    for ev in dmesg_events + journal_events:
        key = (ev.pid, ev.name)
        existing = seen.get(key)
        if existing is None or (ev.total_vm_kb is not None and existing.total_vm_kb is None):
            seen[key] = ev
    report.events = list(seen.values())
    report.total_events = len(report.events)

    # Find most-killed process name
    if report.events:
        name_counts: dict[str, int] = {}
        for ev in report.events:
            name_counts[ev.name] = name_counts.get(ev.name, 0) + 1
        report.most_killed_process = max(name_counts, key=name_counts.get)  # type: ignore[arg-type]

    return report
