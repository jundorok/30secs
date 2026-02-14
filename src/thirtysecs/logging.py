from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach structured extras if present
        for key in ("request_id", "path", "method", "code"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(*, level: str | None = None) -> None:
    """Idempotent logging setup.

    - JSON logs to stdout (Lambda-friendly).
    - Respects LOG_LEVEL env var.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    root = logging.getLogger()
    root.setLevel(log_level)

    # Replace handlers to avoid duplicate logs in Lambda re-use scenarios.
    root.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    _CONFIGURED = True
