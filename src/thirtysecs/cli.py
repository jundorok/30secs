"""CLI interface for 30secs system monitoring tool."""

from __future__ import annotations

import argparse
import sys

from .commands.health import cmd_health, cmd_version
from .commands.inspect import cmd_inspect
from .commands.leak import add_leak_parser
from .commands.oom import add_oom_parser
from .commands.snapshot import cmd_quick, cmd_snapshot, cmd_watch
from .config import settings
from .logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    examples = (
        "Examples:\n"
        "  30secs snapshot -f table\n"
        "  30secs watch -f table -i 5 --alerts\n"
        "  30secs inspect 12345 -f json\n"
        "  30secs leak top -i 1 -n 20 -l 5\n"
        "  30secs leak 12345 -i 2 -n 30\n"
        '  30secs leak --deep-python --script app.py --script-args "--mode stress"\n'
        "  30secs oom                                  # show OOM killer events\n"
        "  30secs oom -f json -o oom.json              # save OOM report as JSON\n"
    )
    parser = argparse.ArgumentParser(
        prog="30secs",
        description="Ultra-lightweight system monitoring tool",
        epilog=examples,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--version",
        "-V",
        action="store_true",
        help="Show version and exit",
    )

    subparsers = parser.add_subparsers(dest="command", title="Commands")

    # ── shared argument helpers ──────────────────────────────────────

    def add_common_args(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--format", "-f",
            choices=["json", "table", "prometheus"],
            default="json",
            help="Output format (default: json)",
        )
        p.add_argument("--output", "-o", type=str, default=None, help="Output file (default: stdout)")
        p.add_argument("--no-processes", action="store_true", help="Exclude process information")
        p.add_argument("--no-network", action="store_true", help="Exclude network information")
        p.add_argument("--no-disk", action="store_true", help="Exclude disk information")
        p.add_argument("--alerts", action="store_true", help="Enable alert checking")

    # ── snapshot ─────────────────────────────────────────────────────

    p_snapshot = subparsers.add_parser("snapshot", help="Take a single system snapshot")
    add_common_args(p_snapshot)
    p_snapshot.set_defaults(func=cmd_snapshot)

    # ── watch ────────────────────────────────────────────────────────

    p_watch = subparsers.add_parser("watch", help="Continuously monitor system metrics")
    add_common_args(p_watch)
    p_watch.add_argument(
        "--interval", "-i",
        type=float,
        default=settings.default_interval_seconds,
        help=f"Interval in seconds (default: {settings.default_interval_seconds})",
    )
    p_watch.add_argument(
        "--count", "-n",
        type=int,
        default=0,
        help="Number of snapshots to take (default: unlimited)",
    )
    p_watch.set_defaults(func=cmd_watch)

    # ── quick ────────────────────────────────────────────────────────

    p_quick = subparsers.add_parser("quick", help="Quick snapshot without processes (faster)")
    add_common_args(p_quick)
    p_quick.set_defaults(func=cmd_quick)

    # ── inspect ──────────────────────────────────────────────────────

    p_inspect = subparsers.add_parser("inspect", help="Inspect a specific process in detail")
    p_inspect.add_argument("pid", type=int, help="Process ID to inspect")
    p_inspect.add_argument(
        "--format", "-f",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )
    p_inspect.set_defaults(func=cmd_inspect)

    # ── leak ─────────────────────────────────────────────────────────

    add_leak_parser(subparsers)

    # ── oom ──────────────────────────────────────────────────────────

    add_oom_parser(subparsers)

    # ── health / version ─────────────────────────────────────────────

    p_health = subparsers.add_parser("health", help="Health check endpoint")
    p_health.set_defaults(func=cmd_health)

    p_version = subparsers.add_parser("version", help="Show version")
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
