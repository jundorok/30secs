"""
thirtysecs

Ultra-lightweight system monitoring tool.

Why `thirtysecs`?
  - Python identifiers can't start with a digit, but distribution names can.
  - So: project/distribution name = "30secs", import package = "thirtysecs".
"""

from __future__ import annotations

from .core import collect_quick_snapshot, collect_snapshot

__all__ = ["__version__", "collect_quick_snapshot", "collect_snapshot"]

__version__ = "0.2.2"
