from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from physical_robot.contracts import CommandRequest, CommandType
from physical_robot.products import product_catalog


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


def test_json_schema_exposes_all_command_variants() -> None:
    schema_text = str(CommandRequest.model_json_schema())
    assert "NavigateAction" in schema_text
    assert "ManipulateAction" in schema_text
    assert "ProtectiveStopAction" in schema_text
