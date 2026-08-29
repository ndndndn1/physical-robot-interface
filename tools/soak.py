"""Allocation and bound soak for the no-worker deterministic runtime."""

from __future__ import annotations

import argparse
import gc
import json
import tracemalloc
from datetime import UTC, datetime, timedelta

from physical_robot.clock import ManualClock
from physical_robot.contracts import CommandRequest
from physical_robot.runtime import MockRobotRuntime

MAX_GROWTH_BYTES = 8 * 1024 * 1024


def run(iterations: int) -> dict[str, int | str]:
    if iterations < 1:
        raise ValueError("iterations must be positive")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    runtime = MockRobotRuntime(clock=ManualClock(now), max_commands=128)
    tracemalloc.start()
    gc.collect()
    baseline, _ = tracemalloc.get_traced_memory()
    for index in range(iterations):
        state = runtime.get_state("mm-01-a")
        request = CommandRequest.model_validate(
            {
                "command_id": f"soak-{index}",
                "robot_id": state.robot_id,
                "issued_at": now,
                "expires_at": now + timedelta(hours=1),
                "expected_state_version": state.state_version,
                "action": {
                    "type": "navigate",
                    "target": {"x_m": index % 100, "y_m": 0, "yaw_rad": 0},
                },
            }
        )
        runtime.submit(request)
        runtime.get_command(request.command_id)
        runtime.get_command(request.command_id)
    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    growth = max(0, current - baseline)
    if runtime.command_count > 128:
        raise RuntimeError("command store exceeded configured bound")
    if growth > MAX_GROWTH_BYTES:
        raise RuntimeError(f"allocation growth {growth} exceeded {MAX_GROWTH_BYTES}")
    return {
        "status": "pass",
        "iterations": iterations,
        "retained_commands": runtime.command_count,
        "allocation_growth_bytes": growth,
        "peak_traced_bytes": peak,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=10_000)
    args = parser.parse_args()
    print(json.dumps(run(args.iterations), sort_keys=True))


if __name__ == "__main__":
    main()
