from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppError(Exception):
    """A controlled, user-facing error.

    Use this for validation failures, unsupported routes, etc.
    """

    status_code: int
    code: str
    message: str

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} ({self.status_code}): {self.message}"
