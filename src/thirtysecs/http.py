from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

JsonDict = dict[str, Any]


@dataclass(slots=True)
class ApiResponse:
    status_code: int
    body: JsonDict | str
    headers: dict[str, str] = field(default_factory=dict)
    is_base64_encoded: bool = False

    def to_lambda_proxy(self) -> dict[str, Any]:
        """Return an AWS Lambda Proxy Integration compatible dict."""
        headers = {"content-type": "application/json; charset=utf-8", **self.headers}
        if isinstance(self.body, str):
            body_str = self.body
        else:
            body_str = json.dumps(self.body, ensure_ascii=False, separators=(",", ":"))
        return {
            "statusCode": int(self.status_code),
            "headers": headers,
            "body": body_str,
            "isBase64Encoded": bool(self.is_base64_encoded),
        }


def json_error(
    status_code: int, code: str, message: str, *, request_id: str | None = None
) -> ApiResponse:
    payload: JsonDict = {"error": {"code": code, "message": message}}
    headers: dict[str, str] = {}
    if request_id:
        headers["x-request-id"] = request_id
    return ApiResponse(status_code=status_code, body=payload, headers=headers)


def json_ok(payload: Mapping[str, Any], *, request_id: str | None = None) -> ApiResponse:
    headers: dict[str, str] = {}
    if request_id:
        headers["x-request-id"] = request_id
    return ApiResponse(status_code=200, body=dict(payload), headers=headers)
