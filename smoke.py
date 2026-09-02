#!/usr/bin/env python3
"""Safe localhost-only smoke for the deterministic mock container."""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

BASE_URL = "http://127.0.0.1:8080"


def request(path: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"content-type": "application/json"} if data is not None else {}
    operation = urllib.request.Request(
        BASE_URL + path, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(operation, timeout=5) as response:
            return json.load(response)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"localhost smoke request failed for {path}: {exc}") from exc


def main() -> int:
    if request("/healthz") != {"status": "ok"}:
        raise RuntimeError("health response did not match the contract")
    products = request("/v1/products")
    if {item["model_name"] for item in products} != {"MH-01", "MM-01"}:
        raise RuntimeError("product catalog did not contain both mock profiles")
    capability_profiles = request("/v2/products")
    if {item["model_name"] for item in capability_profiles} != {"MH-01", "MM-01"}:
        raise RuntimeError("v2 capability catalog did not contain both mock profiles")
    for profile_item in capability_profiles:
        claimed = profile_item.pop("profile_digest")
        canonical = json.dumps(
            profile_item, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode()
        actual = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
        if claimed != actual:
            raise RuntimeError("v2 capability profile digest did not verify")
        profile_item["profile_digest"] = claimed
    state = request("/v1/robots/mm-01-a")
    profile = next(item for item in capability_profiles if item["model_name"] == "MM-01")
    now = datetime.now(UTC)
    rejected_id = f"smoke-limit-{uuid.uuid4().hex}"
    rejected = request(
        "/v1/commands",
        method="POST",
        body={
            "contract_version": "1.0.0",
            "command_id": rejected_id,
            "robot_id": state["robot_id"],
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=30)).isoformat(),
            "expected_state_version": state["state_version"],
            "action": {
                "type": "navigate",
                "target": {"x_m": 0.25, "y_m": 0.0, "yaw_rad": 0.0},
                "max_speed_mps": profile["max_navigation_speed_mps"] + 0.01,
            },
        },
    )
    if rejected["status"] != "rejected" or rejected["error_code"] != "speed_limit_exceeded":
        raise RuntimeError("mock did not enforce the v2 navigation speed limit")
    if request("/v1/robots/mm-01-a")["state_version"] != state["state_version"]:
        raise RuntimeError("rejected limit probe changed robot state")
    command_id = f"smoke-{uuid.uuid4().hex}"
    command = {
        "contract_version": "1.0.0",
        "command_id": command_id,
        "robot_id": state["robot_id"],
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=30)).isoformat(),
        "expected_state_version": state["state_version"],
        "action": {
            "type": "navigate",
            "target": {"x_m": 0.25, "y_m": 0.0, "yaw_rad": 0.0},
        },
    }
    accepted = request("/v1/commands", method="POST", body=command)
    duplicate = request("/v1/commands", method="POST", body=command)
    if accepted != duplicate or accepted["status"] != "accepted":
        raise RuntimeError("idempotent submit contract failed")
    running = request(f"/v1/commands/{command_id}")
    completed = request(f"/v1/commands/{command_id}")
    if running["status"] != "running" or completed["status"] != "completed":
        raise RuntimeError("command lifecycle contract failed")
    print(
        json.dumps(
            {
                "status": "pass",
                "robot_id": state["robot_id"],
                "profile_digest": profile["profile_digest"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
