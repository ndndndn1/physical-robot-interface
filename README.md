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

## Development

Requires Python 3.12 and `uv`:

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy
```

Runtime and client examples are documented after the API implementation below in this
repository's `docs/` directory.
