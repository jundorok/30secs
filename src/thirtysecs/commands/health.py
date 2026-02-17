"""Health and version command handlers."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime

from ..config import settings


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
    from .. import __version__

    sys.stdout.write(f"30secs version {__version__}\n")
    return 0
