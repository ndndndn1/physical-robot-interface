"""Deterministic in-process command throughput benchmark."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import UTC, datetime, timedelta

from physical_robot.clock import ManualClock
from physical_robot.contracts import CommandRequest
from physical_robot.runtime import MockRobotRuntime


def run(iterations: int) -> dict[str, float | int]:
    if iterations < 1:
        raise ValueError("iterations must be positive")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    runtime = MockRobotRuntime(clock=ManualClock(now), max_commands=256)
    durations_ms: list[float] = []
    started = time.perf_counter()
    for index in range(iterations):
        state = runtime.get_state("mh-01-a")
        request = CommandRequest.model_validate(
            {
                "command_id": f"bench-{index}",
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
        item_started = time.perf_counter()
        runtime.submit(request)
        runtime.get_command(request.command_id)
        runtime.get_command(request.command_id)
        durations_ms.append((time.perf_counter() - item_started) * 1_000)
    elapsed = time.perf_counter() - started
    ordered = sorted(durations_ms)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    return {
        "iterations": iterations,
        "elapsed_seconds": round(elapsed, 6),
        "cycles_per_second": round(iterations / elapsed, 2),
        "mean_cycle_ms": round(statistics.mean(durations_ms), 4),
        "p95_cycle_ms": round(p95, 4),
        "retained_commands": runtime.command_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=2_000)
    parser.add_argument("--min-cycles-per-second", type=float, default=2_000)
    args = parser.parse_args()
    result = run(args.iterations)
    print(json.dumps(result, sort_keys=True))
    if result["cycles_per_second"] < args.min_cycles_per_second:
        raise SystemExit("benchmark throughput is below the required minimum")


if __name__ == "__main__":
    main()
