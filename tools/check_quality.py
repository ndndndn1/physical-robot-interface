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

    categories = scorecard.get("categories", [])
    total_weight = sum(item["weight"] for item in categories)
    total_score = sum(item["score"] for item in categories)
    if total_weight != 100:
        raise ValueError(f"category weights total {total_weight}, expected 100")
    covered: set[str] = set()
    for category in categories:
        if not 0 <= category["score"] <= category["weight"]:
            raise ValueError(f"invalid score for {category['name']}")
        covered.update(category["requirements"])
    missing = ids - covered
    unknown = covered - ids
    if missing or unknown:
        raise ValueError(f"coverage mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}")
    threshold = scorecard.get("threshold")
    if not isinstance(threshold, int) or total_score < threshold:
        raise ValueError(f"quality score {total_score} is below threshold {threshold}")
    return total_score


def main() -> None:
    score = check_quality()
    print(json.dumps({"quality_score": score, "maximum": 100, "status": "pass"}))


if __name__ == "__main__":
    main()
