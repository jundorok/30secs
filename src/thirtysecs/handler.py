from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from .errors import AppError
from .http import ApiResponse, json_error, json_ok
from .logging import configure_logging
from .core import collect_snapshot

log = logging.getLogger(__name__)


def _get_case_insensitive(headers: Mapping[str, str] | None, key: str) -> str | None:
    if not headers:
        return None
    if key in headers:
        return headers[key]
    lower = key.lower()
    for k, v in headers.items():
        if k.lower() == lower:
            return v
    return None


def _extract_request_id(event: Mapping[str, Any], context: Any) -> str:
    """Extract a correlation id for logs + responses."""
    try:
        rc = event.get("requestContext") or {}
        if isinstance(rc, dict):
            rid = rc.get("requestId")
            if isinstance(rid, str) and rid:
                return rid
    except Exception:
        pass

    headers = event.get("headers")
    if isinstance(headers, dict):
        hdr = _get_case_insensitive(headers, "x-request-id")
        if hdr:
            return str(hdr)

    aws_rid = getattr(context, "aws_request_id", None)
    if isinstance(aws_rid, str) and aws_rid:
        return aws_rid

    return "unknown"


def _extract_method_path(event: Mapping[str, Any]) -> tuple[str, str]:
    """Support API Gateway v2/v1 shapes (best-effort)."""
    rc = event.get("requestContext")
    if isinstance(rc, dict):
        http = rc.get("http")
        if isinstance(http, dict):
            method = http.get("method")
            path = http.get("path")
            if isinstance(method, str) and isinstance(path, str):
                return method.upper(), path

    method = event.get("httpMethod")
    path = event.get("path")
    if isinstance(method, str) and isinstance(path, str):
        return method.upper(), path

    raw_path = event.get("rawPath")
    if isinstance(raw_path, str):
        return "GET", raw_path

    raise AppError(
        status_code=400,
        code="bad_request",
        message="Could not determine HTTP method/path from event.",
    )


def _route(method: str, path: str, *, request_id: str) -> ApiResponse:
    if method != "GET":
        raise AppError(status_code=405, code="method_not_allowed", message="Only GET is supported.")

    if path == "/healthz":
        return json_ok({"ok": True}, request_id=request_id)

    if path == "/v1/snapshot":
        snap = collect_snapshot()
        return json_ok({"snapshot": snap}, request_id=request_id)

    raise AppError(status_code=404, code="not_found", message="No route matches the request.")


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint (Lambda proxy response)."""
    configure_logging()
    request_id = _extract_request_id(event, context)

    try:
        method, path = _extract_method_path(event)
        log.info("request", extra={"request_id": request_id, "method": method, "path": path})

        resp = _route(method, path, request_id=request_id)
        return resp.to_lambda_proxy()

    except AppError as e:
        log.warning("handled_error", extra={"request_id": request_id, "code": e.code})
        return json_error(e.status_code, e.code, e.message, request_id=request_id).to_lambda_proxy()

    except Exception:
        log.exception("unhandled_error", extra={"request_id": request_id})
        return json_error(
            500, "internal_error", "Unexpected server error.", request_id=request_id
        ).to_lambda_proxy()
