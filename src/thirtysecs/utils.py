"""Shared utility functions."""

from __future__ import annotations

import os
import sys


def bytes_to_human(n: int | float) -> str:
    """Convert bytes to human-readable string (e.g. 1.00 MB)."""
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024.0:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} PB"


def output_text(data: str, output_file: str | None = None) -> None:
    """Write *data* to *output_file* (append) or stdout."""
    if output_file:
        mode = "a" if os.path.exists(output_file) else "w"
        with open(output_file, mode) as f:
            f.write(data + "\n")
    else:
        sys.stdout.write(data + "\n")
        sys.stdout.flush()
