from __future__ import annotations

import json

from thirtysecs.handler import lambda_handler


def _event(path: str) -> dict:
    return {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {"http": {"method": "GET", "path": path}, "requestId": "req-123"},
        "headers": {"x-request-id": "req-123"},
    }


def test_healthz():
    resp = lambda_handler(_event("/healthz"), context=None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True


def test_snapshot():
    resp = lambda_handler(_event("/v1/snapshot"), context=None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "snapshot" in body
    assert "cpu" in body["snapshot"]
