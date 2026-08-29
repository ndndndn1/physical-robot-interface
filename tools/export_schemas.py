"""Export deterministic public JSON Schemas from the canonical Pydantic models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from physical_robot.contracts import CommandRecord, CommandRequest, RobotState
from physical_robot.products import ProductProfile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = Path("contracts")
    if not args.check:
        target.mkdir(exist_ok=True)
    models = {
        "command-record": CommandRecord,
        "command-request": CommandRequest,
        "product-profile": ProductProfile,
        "robot-state": RobotState,
    }
    for name, model in models.items():
        content = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        path = target / f"{name}.schema.json"
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"{path} is stale")
        else:
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
