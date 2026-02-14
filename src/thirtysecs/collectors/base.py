"""Base collector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    """Abstract base class for all metric collectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Collector name used as key in snapshot."""
        ...

    @abstractmethod
    def collect(self) -> dict[str, Any]:
        """Collect and return metrics as a dictionary."""
        ...
