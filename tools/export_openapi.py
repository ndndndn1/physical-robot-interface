"""Export the deterministic OpenAPI document."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from physical_robot.api import app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    target = Path("contracts/openapi.json")
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != content:
            raise SystemExit("contracts/openapi.json is stale")
        return
    target.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
