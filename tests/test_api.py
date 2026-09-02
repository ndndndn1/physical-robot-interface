from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from physical_robot.api import create_app
from physical_robot.client import RobotClient
from physical_robot.clock import ManualClock
from physical_robot.conformance import run_conformance
from physical_robot.contracts import (
    CommandRequest,
    CommandStatus,
    HardwareSafetyState,
    HardwareStatePatch,
)
from physical_robot.runtime import MockRobotRuntime

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_command(command_id: str, state_version: int = 0) -> dict[str, object]:
    return {
        "command_id": command_id,
        "robot_id": "mh-01-a",
        "issued_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(seconds=30)).isoformat(),
        "expected_state_version": state_version,
        "action": {
            "type": "navigate",
            "target": {"x_m": 1, "y_m": 2, "yaw_rad": 0},
        },
    }


def test_rest_catalog_state_and_command_lifecycle() -> None:
    app = create_app(MockRobotRuntime(clock=ManualClock(NOW)))
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert len(client.get("/v1/products").json()) == 2
        v2_products = client.get("/v2/products")
        assert v2_products.status_code == 200
        assert {item["model_name"] for item in v2_products.json()} == {"MH-01", "MM-01"}
        assert all(item["profile_digest"].startswith("sha256:") for item in v2_products.json())
        assert {item["robot_id"] for item in client.get("/v1/robots").json()} == {
            "mh-01-a",
            "mm-01-a",
        }

        submitted = client.post("/v1/commands", json=make_command("api-command"))
        assert submitted.status_code == 202
        assert submitted.json()["status"] == "accepted"
        assert client.get("/v1/commands/api-command").json()["status"] == "running"
        assert client.get("/v1/commands/api-command").json()["status"] == "completed"


def test_api_has_stable_error_envelope_and_openapi_contract() -> None:
    app = create_app(MockRobotRuntime(clock=ManualClock(NOW)))
    with TestClient(app) as client:
        not_found = client.get("/v1/robots/missing")
        assert not_found.status_code == 404
        assert not_found.json() == {
            "code": "not_found",
            "message": "robot missing was not found",
        }

        invalid = client.post("/v1/commands", json={"command_id": "incomplete"})
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "validation_error"

        schema = client.get("/openapi.json").json()
        assert "/v1/commands" in schema["paths"]
        assert "CommandRequest" in schema["components"]["schemas"]
        assert "/v2/products" in schema["paths"]
        assert "ProductCapabilityProfile" in schema["components"]["schemas"]


def test_client_sdk_round_trip_and_hardware_state() -> None:
    app = create_app(MockRobotRuntime(clock=ManualClock(NOW)))
    with TestClient(app) as transport, RobotClient(client=transport) as client:
        profiles = client.product_capabilities()
        assert len(profiles) == 2
        assert client.product_capability("mock-humanoid-mh-01") == profiles[0]
        request = CommandRequest.model_validate(make_command("sdk-command"))
        assert client.submit(request).status is CommandStatus.ACCEPTED
        assert client.command("sdk-command").status is CommandStatus.RUNNING
        assert client.cancel("sdk-command").status is CommandStatus.CANCELLED

        state = client.simulate_hardware(
            "mm-01-a", HardwareStatePatch(hardware_estop_engaged=True)
        )
        assert state.hardware_safety_state is HardwareSafetyState.ESTOP_ENGAGED


def test_black_box_conformance_is_read_only_by_default_and_opt_in_for_commands() -> None:
    app = create_app(MockRobotRuntime())
    with TestClient(app) as transport, RobotClient(client=transport) as client:
        read_only = run_conformance(client, "mh-01-a")
        assert read_only.passed
        assert read_only.checks[-1].detail.startswith("skipped safely")

        active = run_conformance(client, "mm-01-a", allow_command_test=True)
        assert active.passed
        assert {check.name for check in active.checks} >= {
            "capability-profile-v2",
            "target-capability-profile",
            "idempotent-submit",
            "lifecycle",
        }
