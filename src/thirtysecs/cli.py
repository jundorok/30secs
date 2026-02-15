"""CLI interface for 30secs system monitoring tool."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import UTC, datetime
from typing import Any

from .alerts import get_default_alert_checker
from .commands.leak import add_leak_parser
from .config import settings
from .core import collect_quick_snapshot, collect_snapshot
from .formatters import get_formatter
from .logging import configure_logging

# Graceful shutdown flag
_shutdown_requested = False


def _signal_handler(signum: int, frame: Any) -> None:
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    _shutdown_requested = True
    sys.stderr.write("\n[30secs] Shutdown requested, exiting gracefully...\n")


def _output(data: str, output_file: str | None = None) -> None:
    """Write output to stdout or file."""
    if output_file:
        mode = "a" if os.path.exists(output_file) else "w"
        with open(output_file, mode) as f:
            f.write(data + "\n")
    else:
        sys.stdout.write(data + "\n")
        sys.stdout.flush()


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Take a single snapshot."""
    snapshot = collect_snapshot(
        include_processes=not args.no_processes,
        include_network=not args.no_network,
        include_disk=not args.no_disk,
    )

    formatter = get_formatter(args.format)
    output = formatter.format(snapshot)
    _output(output, args.output)

    # Check alerts if enabled
    if args.alerts:
        checker = get_default_alert_checker()
        alerts = checker.check(snapshot)
        if alerts:
            return 1  # Exit with error if alerts triggered

    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Continuously watch system metrics."""
    global _shutdown_requested

    interval = float(args.interval)
    if interval <= 0:
        sys.stderr.write("Error: --interval must be > 0\n")
        return 2

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    formatter = get_formatter(args.format)
    alert_checker = get_default_alert_checker() if args.alerts else None

    count = 0
    max_count = args.count if args.count > 0 else float("inf")

    while not _shutdown_requested and count < max_count:
        snapshot = collect_snapshot(
            include_processes=not args.no_processes,
            include_network=not args.no_network,
            include_disk=not args.no_disk,
        )

        # Clear screen for table format
        if args.format == "table" and not args.output:
            sys.stdout.write("\033[2J\033[H")  # ANSI clear screen

        output = formatter.format(snapshot)
        _output(output, args.output)

        # Check alerts
        if alert_checker:
            alerts = alert_checker.check(snapshot)
            if alerts and args.format != "table":
                for alert in alerts:
                    sys.stderr.write(f"⚠️  ALERT: {alert.message}\n")

        count += 1

        if count < max_count and not _shutdown_requested:
            time.sleep(interval)

    return 0


def cmd_quick(args: argparse.Namespace) -> int:
    """Quick snapshot without processes (faster)."""
    snapshot = collect_quick_snapshot()
    formatter = get_formatter(args.format)
    output = formatter.format(snapshot)
    _output(output, args.output)
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """Inspect a specific process in detail."""
    from .collectors.process import get_process_detail

    pid = args.pid
    detail = get_process_detail(pid)

    if detail is None:
        sys.stderr.write(f"Error: Process {pid} not found\n")
        return 1

    if "error" in detail and detail.get("error") == "Access denied":
        sys.stderr.write(f"Error: Access denied for process {pid}\n")
        return 1

    if args.format == "json":
        sys.stdout.write(json.dumps(detail, indent=2, default=str) + "\n")
    else:
        _print_process_detail(detail)

    return 0


def _print_process_detail(detail: dict[str, Any]) -> None:
    """Print process detail in human-readable format."""
    lines = [
        "=" * 60,
        f"  Process Detail - PID {detail['pid']}",
        "=" * 60,
        "",
        "📌 BASIC INFO",
        f"  Name:        {detail.get('name', 'N/A')}",
        f"  Status:      {detail.get('status', 'N/A')}",
        f"  User:        {detail.get('username', 'N/A')}",
        f"  Created:     {detail.get('create_time', 'N/A')}",
        f"  Command:     {detail.get('cmdline', 'N/A')[:80]}",
    ]

    if detail.get("cwd"):
        lines.append(f"  Working Dir: {detail['cwd']}")

    if detail.get("parent"):
        lines.append(f"  Parent:      {detail['parent']['name']} (PID {detail['parent']['pid']})")

    # Memory
    mem = detail.get("memory", {})
    if "error" not in mem:
        lines.extend(
            [
                "",
                "💾 MEMORY",
                f"  RSS:         {mem.get('rss_human', 'N/A')} ({mem.get('percent', 0):.1f}%)",
                f"  VMS:         {mem.get('vms_human', 'N/A')}",
            ]
        )
        if mem.get("uss_human"):
            lines.append(f"  USS:         {mem.get('uss_human', 'N/A')} (unique to this process)")
        if mem.get("pss_human"):
            lines.append(f"  PSS:         {mem.get('pss_human', 'N/A')} (proportional share)")

    # CPU & Threads
    cpu = detail.get("cpu", {})
    threads = detail.get("threads", {})
    lines.extend(
        [
            "",
            "🖥  CPU & THREADS",
            f"  CPU:         {cpu.get('percent', 0):.1f}%",
            f"  Threads:     {threads.get('count', cpu.get('num_threads', 0))}",
        ]
    )

    # Open files
    open_files = detail.get("open_files", {})
    if open_files.get("count", 0) > 0:
        lines.extend(
            [
                "",
                f"📂 OPEN FILES ({open_files['count']} total)",
            ]
        )
        for f in open_files.get("files", [])[:10]:
            lines.append(f"  • {f}")
        if open_files["count"] > 10:
            lines.append(f"  ... and {open_files['count'] - 10} more")

    # Network connections
    conns = detail.get("connections", {})
    if conns.get("count", 0) > 0:
        lines.extend(
            [
                "",
                f"🌐 NETWORK CONNECTIONS ({conns['count']} total)",
            ]
        )
        for c in conns.get("details", [])[:10]:
            laddr = c.get("laddr", "N/A")
            raddr = c.get("raddr", "N/A") or "*"
            status = c.get("status", "")
            lines.append(f"  • {laddr} → {raddr} ({status})")

    # Children
    children = detail.get("children", [])
    if children:
        lines.extend(
            [
                "",
                f"👶 CHILD PROCESSES ({len(children)})",
            ]
        )
        for c in children[:10]:
            lines.append(f"  • PID {c['pid']}: {c['name']}")

    lines.append("")
    sys.stdout.write("\n".join(lines) + "\n")


def cmd_health(args: argparse.Namespace) -> int:
    """Health check endpoint."""
    health = {
        "ok": True,
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "service": settings.service_name,
    }
    sys.stdout.write(json.dumps(health) + "\n")
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Show version."""
    from . import __version__

    sys.stdout.write(f"30secs version {__version__}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        prog="30secs",
        description="Ultra-lightweight system monitoring tool",
    )

    # Global options
    parser.add_argument(
        "--version",
        "-V",
        action="store_true",
        help="Show version and exit",
    )

    subparsers = parser.add_subparsers(dest="command")

    # Common arguments for snapshot commands
    def add_common_args(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--format",
            "-f",
            choices=["json", "table", "prometheus"],
            default="json",
            help="Output format (default: json)",
        )
        p.add_argument(
            "--output",
            "-o",
            type=str,
            default=None,
            help="Output file (default: stdout)",
        )
        p.add_argument(
            "--no-processes",
            action="store_true",
            help="Exclude process information",
        )
        p.add_argument(
            "--no-network",
            action="store_true",
            help="Exclude network information",
        )
        p.add_argument(
            "--no-disk",
            action="store_true",
            help="Exclude disk information",
        )
        p.add_argument(
            "--alerts",
            action="store_true",
            help="Enable alert checking",
        )

    # snapshot command
    p_snapshot = subparsers.add_parser(
        "snapshot",
        help="Take a single system snapshot",
    )
    add_common_args(p_snapshot)
    p_snapshot.set_defaults(func=cmd_snapshot)

    # watch command
    p_watch = subparsers.add_parser(
        "watch",
        help="Continuously monitor system metrics",
    )
    add_common_args(p_watch)
    p_watch.add_argument(
        "--interval",
        "-i",
        type=float,
        default=settings.default_interval_seconds,
        help=f"Interval in seconds (default: {settings.default_interval_seconds})",
    )
    p_watch.add_argument(
        "--count",
        "-n",
        type=int,
        default=0,
        help="Number of snapshots to take (default: unlimited)",
    )
    p_watch.set_defaults(func=cmd_watch)

    # quick command
    p_quick = subparsers.add_parser(
        "quick",
        help="Quick snapshot without processes (faster)",
    )
    add_common_args(p_quick)
    p_quick.set_defaults(func=cmd_quick)

    # inspect command
    p_inspect = subparsers.add_parser(
        "inspect",
        help="Inspect a specific process in detail",
    )
    p_inspect.add_argument(
        "pid",
        type=int,
        help="Process ID to inspect",
    )
    p_inspect.add_argument(
        "--format",
        "-f",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )
    p_inspect.set_defaults(func=cmd_inspect)

    # leak command
    add_leak_parser(subparsers)

    # health command
    p_health = subparsers.add_parser(
        "health",
        help="Health check endpoint",
    )
    p_health.set_defaults(func=cmd_health)

    # version command
    p_version = subparsers.add_parser(
        "version",
        help="Show version",
    )
    p_version.set_defaults(func=cmd_version)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        from . import __version__

        sys.stdout.write(f"30secs version {__version__}\n")
        raise SystemExit(0)

    if not args.command:
        parser.print_help()
        raise SystemExit(0)

    rc = int(args.func(args))
    raise SystemExit(rc)
