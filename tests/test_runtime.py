from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from physical_robot.clock import ManualClock
from physical_robot.contracts import (
    CommandRequest,
    CommandStatus,
    CommandType,
    HardwareSafetyState,
    HardwareStatePatch,
)
from physical_robot.errors import CapacityError, ConflictError, NotFoundError
from physical_robot.products import product_catalog
from physical_robot.runtime import MockRobotRuntime

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def command(
    command_id: str,
    *,
    robot_id: str = "mh-01-a",
    state_version: int = 0,
    issued_at: datetime = NOW,
    expires_at: datetime = NOW + timedelta(minutes=1),
    action: dict[str, object] | None = None,
) -> CommandRequest:
    return CommandRequest.model_validate(
        {
            "command_id": command_id,
            "robot_id": robot_id,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "expected_state_version": state_version,
            "action": action
            or {
                "type": "navigate",
                "target": {"x_m": 4, "y_m": 2, "yaw_rad": 0},
            },
        }
    )


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(NOW)


@pytest.fixture
def runtime(clock: ManualClock) -> MockRobotRuntime:
    return MockRobotRuntime(clock=clock, max_commands=8)


def test_deterministic_lifecycle_applies_navigation(runtime: MockRobotRuntime) -> None:
    submitted = runtime.submit(command("cmd-life"))
    running = runtime.get_command("cmd-life")
    completed = runtime.get_command("cmd-life")

    assert submitted.status is CommandStatus.ACCEPTED
    assert running.status is CommandStatus.RUNNING
    assert completed.status is CommandStatus.COMPLETED
    assert [item.status for item in completed.transitions] == [
        CommandStatus.SUBMITTED,
        CommandStatus.ACCEPTED,
        CommandStatus.RUNNING,
        CommandStatus.COMPLETED,
    ]
    assert runtime.get_state("mh-01-a").pose.x_m == 4
    assert runtime.get_state("mh-01-a").active_command_id is None


def test_idempotency_returns_same_record_and_changed_payload_conflicts(
    runtime: MockRobotRuntime,
) -> None:
    request = command("cmd-idem")
    first = runtime.submit(request)
    assert runtime.submit(request) == first

    changed = command(
        "cmd-idem",
        action={"type": "navigate", "target": {"x_m": 9, "y_m": 2, "yaw_rad": 0}},
    )
    with pytest.raises(ConflictError, match="different payload") as error:
        runtime.submit(changed)
    assert error.value.code == "idempotency_conflict"


@pytest.mark.parametrize(
    ("input_command", "error_code"),
    [
        (
            command("expired", issued_at=NOW - timedelta(minutes=2), expires_at=NOW),
            "expired_command",
        ),
        (command("stale", state_version=99), "stale_state"),
        (
            command(
                "joints",
                action={"type": "manipulate", "joint_positions_rad": [0.0, 1.0]},
            ),
            "invalid_joint_count",
        ),
    ],
)
def test_invalid_commands_are_stored_as_rejected(
    runtime: MockRobotRuntime, input_command: CommandRequest, error_code: str
) -> None:
    record = runtime.submit(input_command)
    assert record.status is CommandStatus.REJECTED
    assert record.error_code == error_code


@pytest.mark.parametrize(
    ("robot_id", "joint_count", "speed", "force", "joint_position"),
    [
        ("mh-01-a", 12, 1.01, 121.0, 2.81),
        ("mm-01-a", 6, 1.26, 81.0, 3.01),
    ],
)
def test_v2_product_limits_reject_motion_before_execution(
    runtime: MockRobotRuntime,
    robot_id: str,
    joint_count: int,
    speed: float,
    force: float,
    joint_position: float,
) -> None:
    state_version = runtime.get_state(robot_id).state_version
    cases = (
        (
            "speed",
            {
                "type": "navigate",
                "target": {"x_m": 1, "y_m": 0, "yaw_rad": 0},
                "max_speed_mps": speed,
            },
            "speed_limit_exceeded",
        ),
        (
            "force",
            {
                "type": "manipulate",
                "joint_positions_rad": [0.0] * joint_count,
                "max_force_n": force,
            },
            "force_limit_exceeded",
        ),
        (
            "joint",
            {
                "type": "manipulate",
                "joint_positions_rad": [joint_position] + [0.0] * (joint_count - 1),
            },
            "joint_limit_exceeded",
        ),
    )
    for suffix, action, error_code in cases:
        rejected = runtime.submit(
            command(
                f"{robot_id}-{suffix}",
                robot_id=robot_id,
                state_version=state_version,
                action=action,
            )
        )
        assert rejected.status is CommandStatus.REJECTED
        assert rejected.error_code == error_code
        assert runtime.get_state(robot_id).state_version == state_version
        assert runtime.get_state(robot_id).active_command_id is None


@pytest.mark.parametrize("robot_id", ["mh-01-a", "mm-01-a"])
def test_v2_product_limit_boundaries_are_accepted(
    clock: ManualClock, robot_id: str
) -> None:
    runtime = MockRobotRuntime(clock=clock)
    state = runtime.get_state(robot_id)
    profile = runtime.get_capability_profile(state.product_id)
    accepted = runtime.submit(
        command(
            f"{robot_id}-boundary",
            robot_id=robot_id,
            state_version=state.state_version,
            action={
                "type": "manipulate",
                "joint_positions_rad": [
                    limit.max_position_rad for limit in profile.joint_limits
                ],
                "max_force_n": profile.max_manipulation_force_n,
            },
        )
    )
    assert accepted.status is CommandStatus.ACCEPTED


def test_simulator_hardware_patch_rejects_out_of_profile_joint_state(
    runtime: MockRobotRuntime,
) -> None:
    with pytest.raises(ConflictError) as error:
        runtime.simulate_hardware_state(
            "mm-01-a", HardwareStatePatch(joint_positions_rad=[3.01] + [0.0] * 5)
        )
    assert error.value.code == "joint_limit_exceeded"


def test_cancel_releases_robot(runtime: MockRobotRuntime) -> None:
    accepted = runtime.submit(command("cancel-me"))
    state_version = runtime.get_state("mh-01-a").state_version
    assert accepted.status is CommandStatus.ACCEPTED

    cancelled = runtime.cancel("cancel-me")
    assert cancelled.status is CommandStatus.CANCELLED
    assert runtime.get_state("mh-01-a").active_command_id is None
    assert runtime.get_state("mh-01-a").state_version == state_version + 1
    with pytest.raises(ConflictError, match="cannot cancel"):
        runtime.cancel("cancel-me")


def test_hardware_estop_blocks_motion_but_is_not_software_stop(
    runtime: MockRobotRuntime,
) -> None:
    state = runtime.simulate_hardware_state(
        "mm-01-a", HardwareStatePatch(hardware_estop_engaged=True)
    )
    assert state.hardware_safety_state is HardwareSafetyState.ESTOP_ENGAGED
    assert state.software_protective_stop is False

    rejected = runtime.submit(
        command("blocked", robot_id="mm-01-a", state_version=state.state_version)
    )
    assert rejected.status is CommandStatus.REJECTED
    assert rejected.error_code == "hardware_estop_engaged"


def test_hardware_estop_interrupts_an_accepted_motion(runtime: MockRobotRuntime) -> None:
    runtime.submit(command("interrupted"))
    runtime.simulate_hardware_state(
        "mh-01-a", HardwareStatePatch(hardware_estop_engaged=True)
    )

    failed = runtime.get_command("interrupted")
    assert failed.status is CommandStatus.FAILED
    assert failed.error_code == "hardware_estop_engaged"
    assert runtime.get_state("mh-01-a").active_command_id is None
    assert runtime.get_state("mh-01-a").pose.x_m == 0


def test_unsupported_capability_is_rejected_before_execution(clock: ManualClock) -> None:
    humanoid, mobile = product_catalog()
    navigation_only = humanoid.model_copy(
        update={
            "capabilities": frozenset(
                {CommandType.NAVIGATE, CommandType.PROTECTIVE_STOP}
            )
        }
    )
    runtime = MockRobotRuntime(clock=clock, products=(navigation_only, mobile))
    rejected = runtime.submit(
        command(
            "unsupported",
            action={"type": "manipulate", "joint_positions_rad": [0.0] * 12},
        )
    )
    assert rejected.status is CommandStatus.REJECTED
    assert rejected.error_code == "unsupported_capability"
    assert runtime.get_state("mh-01-a").active_command_id is None


def test_runtime_rejects_inconsistent_v1_and_v2_product_metadata(
    clock: ManualClock,
) -> None:
    products = product_catalog()
    baseline = MockRobotRuntime(clock=clock)
    profiles = baseline.capability_catalog()
    inconsistent = profiles[0].model_copy(update={"joint_count": 11})
    with pytest.raises(ValueError, match="joint counts differ"):
        MockRobotRuntime(
            clock=clock,
            products=products,
            capability_profiles=(inconsistent, profiles[1]),
        )


def test_concurrent_duplicate_submit_is_single_idempotent_record(
    runtime: MockRobotRuntime,
) -> None:
    input_command = command("concurrent-idempotency")
    with ThreadPoolExecutor(max_workers=8) as executor:
        records = list(executor.map(runtime.submit, [input_command] * 32))
    assert len(set(record.model_dump_json() for record in records)) == 1
    assert runtime.command_count == 1


def test_store_is_bounded_and_terminal_entries_are_reclaimed(clock: ManualClock) -> None:
    runtime = MockRobotRuntime(clock=clock, max_commands=1, terminal_retention=timedelta(hours=1))
    runtime.submit(command("active"))
    with pytest.raises(CapacityError):
        runtime.submit(command("overflow", robot_id="mm-01-a"))

    runtime.cancel("active")
    runtime.submit(command("replacement", state_version=2))
    assert runtime.command_count == 1
    with pytest.raises(NotFoundError):
        runtime.get_command("active")


def test_retention_cleanup_has_no_background_tasks(clock: ManualClock) -> None:
    runtime = MockRobotRuntime(clock=clock, terminal_retention=timedelta(seconds=5))
    runtime.submit(command("old"))
    runtime.cancel("old")
    clock.advance(timedelta(seconds=6))
    assert runtime.command_count == 0
