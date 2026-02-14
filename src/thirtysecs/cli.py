from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from .config import settings
from .logging import configure_logging
from .metrics import collect_snapshot


def _print_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def cmd_snapshot(_args: argparse.Namespace) -> int:
    _print_json(collect_snapshot())
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    interval = float(args.interval)
    if interval <= 0:
        sys.stderr.write("--interval must be > 0\n")
        return 2

    # Emit an immediate snapshot, then sleep.
    while True:
        _print_json(collect_snapshot())
        time.sleep(interval)

    # unreachable
    # return 0


def cmd_health(_args: argparse.Namespace) -> int:
    _print_json({"ok": True})
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="30secs")
    sub = p.add_subparsers(dest="command", required=True)

    p_snapshot = sub.add_parser("snapshot", help="Print a single system snapshot as JSON.")
    p_snapshot.set_defaults(func=cmd_snapshot)

    p_watch = sub.add_parser("watch", help="Continuously print snapshots as JSON lines.")
    p_watch.add_argument("--interval", type=float, default=settings.default_interval_seconds, help="Seconds (default: 30).")
    p_watch.set_defaults(func=cmd_watch)

    p_health = sub.add_parser("health", help="Print a basic health JSON.")
    p_health.set_defaults(func=cmd_health)

    return p


def main(argv: list[str] | None = None) -> None:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    rc = int(args.func(args))
    raise SystemExit(rc)
