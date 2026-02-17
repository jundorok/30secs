"""OOM event command handler."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from typing import Any

from ..oom import collect_oom_events


def _output(data: str, output_file: str | None = None) -> None:
    """Write output to stdout or file."""
    if output_file:
        mode = "a" if os.path.exists(output_file) else "w"
        with open(output_file, mode) as f:
            f.write(data + "\n")
    else:
        sys.stdout.write(data + "\n")
        sys.stdout.flush()


def _bytes_to_human(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024.0:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} PB"


def _format_oom_table(report: Any) -> str:
    lines: list[str] = [
        "=" * 92,
        "  OOM Killer Event Report",
        "=" * 92,
        f"Total OOM events found: {report.total_events}",
    ]

    if report.most_killed_process:
        lines.append(f"Most killed process: {report.most_killed_process}")

    if report.source_errors:
        for err in report.source_errors:
            lines.append(f"  (source warning: {err})")

    lines.append("")

    if not report.events:
        lines.append("No OOM kill events detected in available logs.")
        lines.append("")
        return "\n".join(lines)

    lines.extend([
        "+------+--------+----------------------+--------------+--------------+--------------+----------+",
        "| #    | PID    | Process              | Total VM     | Anon RSS     | File RSS     | Source   |",
        "+------+--------+----------------------+--------------+--------------+--------------+----------+",
    ])

    for idx, ev in enumerate(report.events, start=1):
        total_vm = _bytes_to_human(ev.total_vm_kb * 1024) if ev.total_vm_kb else "N/A"
        anon_rss = _bytes_to_human(ev.anon_rss_kb * 1024) if ev.anon_rss_kb else "N/A"
        file_rss = _bytes_to_human(ev.file_rss_kb * 1024) if ev.file_rss_kb else "N/A"
        lines.append(
            f"| {idx:>4} | {ev.pid:>6} | {ev.name[:20]:<20} |"
            f" {total_vm:>12} | {anon_rss:>12} | {file_rss:>12} |"
            f" {ev.source:<8} |"
        )

    lines.extend([
        "+------+--------+----------------------+--------------+--------------+--------------+----------+",
        "",
    ])

    # Show cgroup info if available
    cgroup_events = [ev for ev in report.events if ev.memcg]
    if cgroup_events:
        lines.append("Cgroup details:")
        for ev in cgroup_events:
            lines.append(f"  PID {ev.pid} ({ev.name}): memcg={ev.memcg}")
        lines.append("")

    return "\n".join(lines)


def cmd_oom(args: argparse.Namespace) -> int:
    """Show recent OOM killer events from kernel logs."""
    report = collect_oom_events()

    if args.format == "json":
        payload = {
            "total_events": report.total_events,
            "most_killed_process": report.most_killed_process,
            "source_errors": report.source_errors,
            "events": [asdict(ev) for ev in report.events],
        }
        _output(json.dumps(payload, indent=2), args.output)
    else:
        _output(_format_oom_table(report), args.output)

    return 0


def add_oom_parser(subparsers: Any) -> None:
    """Register `oom` subcommand parser."""
    examples = (
        "Examples:\n"
        "  30secs oom\n"
        "  30secs oom -f json\n"
        "  30secs oom -f json -o oom-events.json\n"
    )
    p_oom = subparsers.add_parser(
        "oom",
        help="Show recent OOM killer events from kernel logs (dmesg/journal)",
        description=(
            "Parse kernel OOM kill events from dmesg and systemd journal.\n"
            "Shows which processes were killed by the OOM killer, with memory\n"
            "details and cgroup info (useful for Kubernetes debugging)."
        ),
        epilog=examples,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_oom.add_argument(
        "--format",
        "-f",
        choices=["table", "json"],
        default="table",
        help="Report format (default: table)",
    )
    p_oom.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file (default: stdout)",
    )
    p_oom.set_defaults(func=cmd_oom)
