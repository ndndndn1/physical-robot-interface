from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from physical_robot.products import product_capability_catalog

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
    canonical = subprocess.run(
        [sys.executable, "quality/check_score.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert canonical.stdout.startswith("quality scorecard passed:")


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


def test_benchmark_evidence_is_bound_to_current_capability_profiles() -> None:
    evidence = json.loads((ROOT / "quality/benchmark-evidence.json").read_text())
    digests = {
        profile.model_name: profile.profile_digest
        for profile in product_capability_catalog()
    }
    assert evidence["benchmark"]["profile_digest"] == digests["MH-01"]
    assert evidence["benchmark"]["cycles_per_second"] >= 2_000
    assert evidence["soak"]["profile_digest"] == digests["MM-01"]
    assert evidence["soak"]["retained_commands"] <= 128
    assert (
        evidence["soak"]["allocation_growth_bytes"]
        <= evidence["soak"]["maximum_growth_bytes"]
    )


def test_runtime_evidence_is_bound_to_current_capability_profile() -> None:
    evidence = json.loads((ROOT / "quality/runtime-evidence.json").read_text())
    digests = {
        profile.model_name: profile.profile_digest
        for profile in product_capability_catalog()
    }
    assert evidence["image_build"] == "pass"
    assert evidence["health"] == "healthy"
    assert evidence["smoke"]["profile_digest"] == digests["MM-01"]
    assert evidence["container"] == {
        "user": "65532:65532",
        "read_only_rootfs": True,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
    }
    assert evidence["cleanup"] == "pass"
