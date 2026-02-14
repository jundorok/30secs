"""CLI interface for 30secs system monitoring tool."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime
from typing import Any

from .alerts import get_default_alert_checker
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


def cmd_health(args: argparse.Namespace) -> int:
    """Health check endpoint."""
    health = {
        "ok": True,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
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
