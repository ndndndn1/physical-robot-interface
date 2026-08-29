from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_machine_readable_quality_gate_passes() -> None:
    result = subprocess.run(
        [sys.executable, "tools/check_quality.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == {
        "quality_score": 92,
        "maximum": 100,
        "status": "pass",
    }


def test_generated_contracts_are_current() -> None:
    for tool in ("tools/export_schemas.py", "tools/export_openapi.py"):
        result = subprocess.run(
            [sys.executable, tool, "--check"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert result.stdout == ""
