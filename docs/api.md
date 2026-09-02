# API and SDK usage

## Inputs and outputs

Command and state operations remain under `/v1`; read-only capability metadata is under
`/v2`. All bodies reject unknown fields. Timestamps must include an offset and
`expires_at` must be later than `issued_at`.

| Operation | Input | Output |
|---|---|---|
| `GET /v1/products` | none | product classification, model and capabilities |
| `GET /v2/products` | none | strict capability profiles for both mock products |
| `GET /v2/products/{product_id}` | product ID | one digest-verified capability profile |
| `GET /v1/robots` | none | current state for every mock robot |
| `GET /v1/robots/{robot_id}` | robot ID | one versioned state |
| `POST /v1/commands` | command metadata and discriminated action | accepted or rejected command record |
| `GET /v1/commands/{command_id}` | command ID | record; advances the deterministic mock |
| `POST /v1/commands/{command_id}/cancel` | command ID | cancelled record, or conflict for a terminal command |
| `PATCH /v1/simulator/robots/{robot_id}/hardware-state` | simulated sensor state | updated robot state |

The command action is one of:

- `navigate`: target `x_m`, `y_m`, `yaw_rad`, optional frame and maximum speed.
- `manipulate`: one joint target per profile joint and an optional maximum force.
- `protective_stop`: a human-readable reason.

The service records `submitted`, then either `accepted` or `rejected`. For accepted
mock commands, the first status read produces `running` and the second produces
`completed` or `failed`. Cancellation is valid before a terminal state.

The exact machine-readable schemas are in `contracts/` and `/openapi.json`. A reused
command ID with the same full payload returns the existing record. Reusing it with a
different payload returns HTTP 409. Expired, stale, busy, unsafe, and unsupported
commands are recorded as `rejected` with a stable `error_code`.

The v2 profile contains ordered joint names and position/velocity limits, maximum
manipulation force, navigation speed and payload, base/tool frames, and a
`sha256:<hex>` `profile_digest`. The digest is computed from canonical JSON containing
every other profile field (`ensure_ascii=true`, sorted keys, compact separators). A
consumer must reject a mismatched digest rather than using partially changed limits.

The unchanged v1 command can enforce joint position, force, and navigation speed.
Velocity and payload are declared for upstream planning/admission but are not silently
invented as v1 command fields. Stable rejection codes are `joint_limit_exceeded`,
`force_limit_exceeded`, and `speed_limit_exceeded`.

## Python client

```python
from datetime import UTC, datetime, timedelta

from physical_robot.client import RobotClient
from physical_robot.contracts import CommandRequest

with RobotClient("http://127.0.0.1:8080") as robots:
    capability = robots.product_capability("mock-mobile-manipulator-mm-01")
    state = robots.state("mm-01-a")
    now = datetime.now(UTC)
    request = CommandRequest.model_validate({
        "command_id": "move-001",
        "robot_id": state.robot_id,
        "issued_at": now,
        "expires_at": now + timedelta(seconds=30),
        "expected_state_version": state.state_version,
        "action": {
            "type": "navigate",
            "target": {"x_m": 2.5, "y_m": 1.0, "yaw_rad": 0.0},
        },
    })
    accepted = robots.submit(request)
```

`ProductCapabilityProfile` validation verifies the canonical digest automatically.
Use the advertised `profile_digest` as an immutable planner/cache key; never treat the
human-readable model name alone as a compatibility decision.

Always read state immediately before constructing a command. A stale state version is
rejected instead of silently executing against changed equipment.

## Safety language

`protective_stop` is a software request delivered over the ordinary application
channel. `hardware_safety_state=estop_engaged` represents an independently observed
hardware input. This interface is not a safety-rated controller and must not replace
hardwired E-stop circuits, safety PLCs, interlocks, or the manufacturer's procedure.
