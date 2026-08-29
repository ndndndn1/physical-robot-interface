"""Fail closed when requirements, evidence, weights, or release score drift."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def check_quality() -> int:
    requirements_data = load_json(ROOT / "quality/requirements.json")
    coverage_data = load_json(ROOT / "requirements-coverage.json")
    scorecard = load_json(ROOT / "quality/scorecard.json")
    requirements = requirements_data.get("requirements", [])
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("requirements must be a non-empty list")
    ids = {item["id"] for item in requirements}
    if len(ids) != len(requirements):
        raise ValueError("requirement IDs must be unique")
    for item in requirements:
        evidence = item.get("evidence", [])
        if item.get("required") and not evidence:
            raise ValueError(f"{item['id']} has no evidence")
        for relative in evidence:
            if not (ROOT / relative).is_file():
                raise ValueError(f"{item['id']} evidence does not exist: {relative}")

    coverage = coverage_data.get("requirements", [])
    if not isinstance(coverage, list) or not coverage:
        raise ValueError("requirements coverage must be a non-empty list")
    coverage_ids = {item.get("requirement_id") for item in coverage}
    if coverage_ids != ids:
        raise ValueError(
            f"coverage IDs differ: missing={sorted(ids - coverage_ids)}, "
            f"unknown={sorted(coverage_ids - ids)}"
        )
    for item in coverage:
        if (
            item.get("kind") == "required"
            and item.get("technical")
            and item.get("coverage") != "full"
        ):
            raise ValueError(f"{item['requirement_id']} is not fully covered")
        if not item.get("tests"):
            raise ValueError(f"{item['requirement_id']} has no tests")
        for relative in item.get("evidence", []):
            if not (ROOT / relative).is_file():
                raise ValueError(
                    f"{item['requirement_id']} coverage evidence does not exist: {relative}"
                )

    categories = scorecard.get("categories", [])
    total_weight = sum(item["max"] for item in categories)
    total_score = sum(item["earned"] for item in categories)
    if total_weight != 100:
        raise ValueError(f"category weights total {total_weight}, expected 100")
    for category in categories:
        if not 0 <= category["earned"] <= category["max"]:
            raise ValueError(f"invalid score for {category['id']}")
        if not category.get("evidence"):
            raise ValueError(f"{category['id']} has no score evidence")
    if scorecard.get("schema_version") != "1.0" or scorecard.get("score") != total_score:
        raise ValueError("canonical scorecard schema or score total is invalid")
    threshold = scorecard.get("target")
    if not isinstance(threshold, int) or total_score < threshold:
        raise ValueError(f"quality score {total_score} is below threshold {threshold}")
    required_gates = {"tests", "runtime_smoke", "memory", "security", "docs_examples"}
    hard_gates = scorecard.get("hard_gates")
    if not isinstance(hard_gates, dict) or set(hard_gates) != required_gates:
        raise ValueError("hard gate keys do not match the shared contract")
    if any(value is not True for value in hard_gates.values()):
        raise ValueError("not all hard gates passed")
    return total_score


def main() -> None:
    score = check_quality()
    print(json.dumps({"quality_score": score, "maximum": 100, "status": "pass"}))


if __name__ == "__main__":
    main()
