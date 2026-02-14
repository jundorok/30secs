from __future__ import annotations

import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "30secs")
    default_interval_seconds: int = _get_int("DEFAULT_INTERVAL_SECONDS", 30)
    include_hostname: bool = os.getenv("INCLUDE_HOSTNAME", "1") not in {"0", "false", "False"}


settings = Settings()
