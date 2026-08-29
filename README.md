# physical-robot-interface

Vendor-neutral command contracts and a deterministic, bounded mock runtime for robot
software integration. The package models two test products:

| Product classification | Product | Model | Connection |
|---|---|---|---|
| Industrial humanoid | MockHumanoid | MH-01 | RobotPort REST v1 |
| Autonomous mobile manipulator | MockMobileManipulator | MM-01 | RobotPort REST v1 |

Both profiles support navigation, manipulation, and a **software protective-stop
request**. A protective-stop request is not a certified hardware emergency stop. The
hardware E-stop state is an independently observed safety input and cannot be cleared
by a normal command.

The same `RobotPort` protocol is implemented by the included mock and is the required
boundary for later ROS 2 or vendor hardware adapters. See `docs/connecting-hardware.md`
before connecting physical equipment.

## Run the mock

```bash
uv sync --extra dev
uv run physical-robot --host 127.0.0.1 --port 8080
```

In another shell, submit a navigation command to a fresh mock instance:

```bash
curl -sS http://127.0.0.1:8080/v1/robots/mh-01-a
issued_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
expires_at=$(date -u -d '+1 minute' +%Y-%m-%dT%H:%M:%SZ)
curl -sS -X POST http://127.0.0.1:8080/v1/commands \
  -H 'content-type: application/json' \
  -d "{\"command_id\":\"demo-001\",\"robot_id\":\"mh-01-a\",\
\"issued_at\":\"${issued_at}\",\"expires_at\":\"${expires_at}\",\
\"expected_state_version\":0,\"action\":{\"type\":\"navigate\",\
\"target\":{\"x_m\":1,\"y_m\":2,\"yaw_rad\":0}}}"
```

For a non-fresh robot, use `state_version` returned by the GET. Poll
`GET /v1/commands/demo-001` twice to observe deterministic `running` and `completed`
states. See [API usage](docs/api.md) for the SDK and failure behavior.

## Container

```bash
docker compose up --build -d
curl --fail http://127.0.0.1:8080/healthz
docker compose down
```

The image runs as a non-root user with a read-only filesystem, no Linux
capabilities, and a localhost-only published port.

## Connect a later adapter

Implement every method in `physical_robot.ports.RobotPort`, expose the same OpenAPI
contract, and run the black-box harness on an isolated test robot:

```bash
uv run physical-robot-conformance --robot-id test-robot
uv run physical-robot-conformance --robot-id test-robot --allow-command-test
```

The command test sends a software protective stop. Never run it on production
equipment. Follow [hardware connection](docs/connecting-hardware.md) for network,
watchdog, namespace, and safety prerequisites.

## Development

Requires Python 3.12 and `uv`:

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy
uv run python tools/check_quality.py
uv run python tools/benchmark.py --iterations 2000
uv run python tools/soak.py --iterations 10000
```

The requirements and evidence-backed 100-point assessment are in
[`docs/enterprise-requirements.md`](docs/enterprise-requirements.md) and
[`quality/scorecard.json`](quality/scorecard.json).
