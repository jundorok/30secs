"""Output formatters."""

from __future__ import annotations

from .base import BaseFormatter
from .json_fmt import JsonFormatter
from .prometheus import PrometheusFormatter
from .table import TableFormatter

__all__ = [
    "BaseFormatter",
    "JsonFormatter",
    "PrometheusFormatter",
    "TableFormatter",
    "get_formatter",
]


def get_formatter(fmt: str) -> BaseFormatter:
    """Get formatter by name."""
    formatters: dict[str, type[BaseFormatter]] = {
        "json": JsonFormatter,
        "table": TableFormatter,
        "prometheus": PrometheusFormatter,
    }

    if fmt not in formatters:
        raise ValueError(f"Unknown format: {fmt}. Available: {', '.join(formatters.keys())}")

    return formatters[fmt]()
