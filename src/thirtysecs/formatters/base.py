"""Base formatter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseFormatter(ABC):
    """Abstract base class for output formatters."""

    @abstractmethod
    def format(self, snapshot: dict[str, Any]) -> str:
        """Format snapshot data to string."""
        ...
