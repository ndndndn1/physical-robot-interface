"""Export deterministic public JSON Schemas from the canonical Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

from physical_robot.contracts import CommandRecord, CommandRequest, RobotState
from physical_robot.products import ProductProfile


def main() -> None:
    target = Path("contracts")
    target.mkdir(exist_ok=True)
    models = {
        "command-record": CommandRecord,
        "command-request": CommandRequest,
        "product-profile": ProductProfile,
        "robot-state": RobotState,
    }
    for name, model in models.items():
        content = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        (target / f"{name}.schema.json").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
