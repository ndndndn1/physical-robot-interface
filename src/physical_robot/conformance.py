"""Black-box RobotPort conformance harness for mock and future hardware adapters."""

from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict

from physical_robot.client import RobotClient
from physical_robot.contracts import CommandRequest, CommandStatus


class ConformanceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    passed: bool
    detail: str


class ConformanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: str
    target_robot_id: str
    checks: tuple[ConformanceCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def run_conformance(
    client: RobotClient, robot_id: str, *, allow_command_test: bool = False
) -> ConformanceReport:
    checks: list[ConformanceCheck] = []
    products = client.products()
    checks.append(
        ConformanceCheck(
            name="catalog",
            passed=bool(products),
            detail=f"received {len(products)} product profiles",
        )
    )
    state = client.state(robot_id)
    checks.append(
        ConformanceCheck(
            name="state",
            passed=state.robot_id == robot_id,
            detail=f"state version {state.state_version}",
        )
    )
    if allow_command_test:
        now = datetime.now(UTC)
        command = CommandRequest.model_validate(
            {
                "command_id": f"conformance-{uuid.uuid4().hex}",
                "robot_id": robot_id,
                "issued_at": now,
                "expires_at": now + timedelta(seconds=30),
                "expected_state_version": state.state_version,
                "action": {
                    "type": "protective_stop",
                    "reason": "adapter conformance test",
                },
            }
        )
        first = client.submit(command)
        duplicate = client.submit(command)
        checks.append(
            ConformanceCheck(
                name="idempotent-submit",
                passed=first == duplicate and first.status is CommandStatus.ACCEPTED,
                detail=f"duplicate returned {duplicate.status}",
            )
        )
        running = client.command(command.command_id)
        completed = client.command(command.command_id)
        checks.append(
            ConformanceCheck(
                name="lifecycle",
                passed=(
                    running.status is CommandStatus.RUNNING
                    and completed.status is CommandStatus.COMPLETED
                ),
                detail=f"observed {running.status} then {completed.status}",
            )
        )
    else:
        checks.append(
            ConformanceCheck(
                name="command-test",
                passed=True,
                detail="skipped safely; pass --allow-command-test only on an isolated test robot",
            )
        )
    return ConformanceReport(
        contract_version="1.0.0", target_robot_id=robot_id, checks=tuple(checks)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a RobotPort adapter")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--robot-id", required=True)
    parser.add_argument("--allow-command-test", action="store_true")
    args = parser.parse_args()
    with RobotClient(args.base_url) as client:
        report = run_conformance(
            client, args.robot_id, allow_command_test=args.allow_command_test
        )
    print(report.model_dump_json(indent=2))
    raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
