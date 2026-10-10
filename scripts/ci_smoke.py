"""Secret-free HTTP smoke checks for the short-lived clean-room CI Web process."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.routes.pages import PAGE_ROUTES


def request(base_url: str, path: str, *, method: str = "GET", payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(base_url + path, data=data, headers=headers, method=method)
    try:
        response = urlopen(req, timeout=5)
    except HTTPError as exc:
        response = exc
    body = response.read().decode("utf-8")
    content_type = response.headers.get_content_type()
    parsed = json.loads(body) if content_type == "application/json" else body
    return response.status, parsed


def main(base_url: str) -> None:
    status, payload = request(base_url, "/api/health/live")
    assert status == 200 and payload["status"] == "live"

    status, payload = request(base_url, "/api/health/ready")
    assert status == 200
    assert payload["checks"]["database"]["status"] == "ok"
    assert payload["checks"]["rpc"] == {
        "status": "unavailable",
        "configured": False,
    }

    assert len(PAGE_ROUTES) == 19
    for route in PAGE_ROUTES:
        status, _ = request(base_url, route)
        assert status == 200, route

    status, payload = request(base_url, "/clean-room-missing-route")
    assert status == 404 and payload["error"]["code"] == "NOT_FOUND"

    status, payload = request(
        base_url,
        "/api/auth/nonce",
        method="POST",
        payload={"wallet_address": "0x1111111111111111111111111111111111111111"},
    )
    assert status == 200 and "message" in payload

    for protected_path in ("/api/me", "/api/dashboard"):
        status, payload = request(base_url, protected_path)
        assert status == 401, protected_path
        assert "error" in payload

    print("clean-room HTTP smoke: PASS (19 pages, health, 404, nonce, auth)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: ci_smoke.py BASE_URL")
    main(sys.argv[1].rstrip("/"))
