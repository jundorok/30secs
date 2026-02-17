"""Snapshot and watch command handlers."""

from __future__ import annotations

import argparse
import signal
import sys
import time
from typing import Any

from ..alerts import get_default_alert_checker
from ..core import collect_quick_snapshot, collect_snapshot
from ..formatters import get_formatter
from ..utils import output_text

# Graceful shutdown flag
_shutdown_requested = False


def _signal_handler(signum: int, frame: Any) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    sys.stderr.write("\n[30secs] Shutdown requested, exiting gracefully...\n")


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Take a single snapshot."""
    snapshot = collect_snapshot(
        include_processes=not args.no_processes,
        include_network=not args.no_network,
        include_disk=not args.no_disk,
    )

    formatter = get_formatter(args.format)
    output_text(formatter.format(snapshot), args.output)

    if args.alerts:
        checker = get_default_alert_checker()
        alerts = checker.check(snapshot)
        if alerts:
            return 1

    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Continuously watch system metrics."""
    global _shutdown_requested

    interval = float(args.interval)
    if interval <= 0:
        sys.stderr.write("Error: --interval must be > 0\n")
        return 2

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

        if args.format == "table" and not args.output:
            sys.stdout.write("\033[2J\033[H")

        output_text(formatter.format(snapshot), args.output)

        if alert_checker:
            alerts = alert_checker.check(snapshot)
            if alerts and args.format != "table":
                for alert in alerts:
                    sys.stderr.write(f"ALERT: {alert.message}\n")

        count += 1

        if count < max_count and not _shutdown_requested:
            time.sleep(interval)

    return 0


def cmd_quick(args: argparse.Namespace) -> int:
    """Quick snapshot without processes (faster)."""
    snapshot = collect_quick_snapshot()
    formatter = get_formatter(args.format)
    output_text(formatter.format(snapshot), args.output)
    return 0
