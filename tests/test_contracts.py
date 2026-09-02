import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from physical_robot.contracts import CommandRequest, CommandType
from physical_robot.products import (
    ProductCapabilityProfile,
    product_capability_catalog,
    product_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
V1_SCHEMA_HASHES = {
    "command-record.schema.json": (
        "e51b897dcb888050f6522b65356642a8df852b30d4c661bb404c7ac95926c94a"
    ),
    "command-request.schema.json": (
        "6bf9236a057c888b248455fca06cf6ce3d7eb01e5542327376cf02ba80ea72cb"
    ),
    "product-profile.schema.json": (
        "0504df713e8a3a623c31a6d6dd4a2feb1a21354bccff50f137ac3c9f397c7e13"
    ),
    "robot-state.schema.json": (
        "48f59c48e13d5c6b616ff49f3d72b5eef2bbb94ef2905b20119876407a27cc1c"
    ),
}


def valid_command() -> dict[str, object]:
    issued = datetime(2026, 1, 1, tzinfo=UTC)
    return {
        "command_id": "cmd-001",
        "robot_id": "mh-01-a",
        "issued_at": issued.isoformat(),
        "expires_at": (issued + timedelta(seconds=30)).isoformat(),
        "expected_state_version": 0,
        "action": {
            "type": "navigate",
            "target": {"x_m": 1.0, "y_m": 2.0, "yaw_rad": 0.5},
        },
    }


def test_command_contract_is_discriminated_and_strict() -> None:
    command = CommandRequest.model_validate(valid_command())
    assert command.action.type is CommandType.NAVIGATE

    payload = valid_command()
    payload["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CommandRequest.model_validate(payload)


def test_command_requires_ordered_timezone_aware_timestamps() -> None:
    payload = valid_command()
    payload["issued_at"] = "2026-01-01T00:00:00"
    with pytest.raises(ValidationError, match="UTC offset"):
        CommandRequest.model_validate(payload)

    payload = valid_command()
    payload["expires_at"] = payload["issued_at"]
    with pytest.raises(ValidationError, match="later than issued_at"):
        CommandRequest.model_validate(payload)


def test_catalog_has_two_explicit_mock_products() -> None:
    products = product_catalog()
    assert {product.model_name for product in products} == {"MH-01", "MM-01"}
    assert all(CommandType.NAVIGATE in product.capabilities for product in products)
    assert all(CommandType.MANIPULATE in product.capabilities for product in products)


def test_v2_capability_profiles_are_complete_immutable_and_digest_verified() -> None:
    profiles = product_capability_catalog()
    assert {profile.model_name for profile in profiles} == {"MH-01", "MM-01"}
    for profile in profiles:
        assert profile.schema_version == "2.0.0"
        assert len(profile.joint_limits) == profile.joint_count
        assert profile.base_frame != profile.tool_frame
        assert profile.max_manipulation_force_n > 0
        assert profile.max_navigation_speed_mps > 0
        assert profile.max_payload_kg > 0
        assert profile.profile_digest.startswith("sha256:")

        tampered = profile.model_dump(mode="json")
        tampered["max_payload_kg"] += 1
        with pytest.raises(ValidationError, match="profile_digest"):
            ProductCapabilityProfile.model_validate(tampered)


def test_v1_schema_snapshots_remain_byte_compatible() -> None:
    for name, expected in V1_SCHEMA_HASHES.items():
        content = (ROOT / "contracts" / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected


def test_json_schema_exposes_all_command_variants() -> None:
    schema_text = str(CommandRequest.model_json_schema())
    assert "NavigateAction" in schema_text
    assert "ManipulateAction" in schema_text
    assert "ProtectiveStopAction" in schema_text
