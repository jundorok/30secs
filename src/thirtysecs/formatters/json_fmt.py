"""JSON formatter."""

from __future__ import annotations

import json
from typing import Any

from .base import BaseFormatter


class JsonFormatter(BaseFormatter):
    """Format snapshot as JSON."""

    def format(self, snapshot: dict[str, Any]) -> str:
        return json.dumps(snapshot, ensure_ascii=False, indent=2)
