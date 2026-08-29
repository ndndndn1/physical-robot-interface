# Enterprise quality scorecard

Release target: at least 80/100 with every hard gate passing.

| Category | Maximum | Certified | Evidence |
|---|---:|---:|---|
| Functionality | 25 | 24 | 22 deterministic tests; two executable product profiles |
| Interface | 20 | 19 | Strict JSON Schema/OpenAPI, typed SDK, adapter conformance harness |
| Reliability and safety | 20 | 18 | Bounded storage, cleanup, concurrency and stop-interruption tests |
| Validation and performance | 15 | 13 | 9,201 cycles/s; 10,000-cycle allocation soak |
| Security and supply chain | 10 | 9 | Hardened local container, pinned base image, CI scanning and SBOM |
| Documentation and usability | 10 | 9 | Runnable examples, I/O guide and hardware handoff procedure |
| **Total** | **100** | **92** | **Target met** |

## Hard gates

| Gate | Result | Evidence |
|---|---|---|
| Tests | Pass | pytest, Ruff and strict mypy |
| Runtime smoke | Pass | localhost container conformance and `smoke.py` |
| Memory | Pass | 10,000 cycles, 128 retained records, 569,808-byte growth |
| Security | Pass | non-root, read-only, all capabilities dropped, localhost port |
| Documentation examples | Pass | fresh-instance curl flow and typed client example |

`quality/check_score.py` verifies the shared scorecard schema and all five hard-gate
keys. `tools/check_quality.py` additionally verifies local evidence files and complete
requirements coverage. Scores must be updated only with evidence from the same commit.
