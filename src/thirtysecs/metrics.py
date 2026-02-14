"""Legacy metrics module - delegates to core.

This module is kept for backwards compatibility.
Use thirtysecs.core for new code.
"""

from __future__ import annotations

from typing import Any

from .core import collect_snapshot as _collect_snapshot


def collect_snapshot() -> dict[str, Any]:
    """Collect a lightweight system snapshot.

    Deprecated: Use thirtysecs.core.collect_snapshot() instead.
    """
    return _collect_snapshot()
