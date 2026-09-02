# Enterprise quality scorecard

Release target: at least 80/100 with every hard gate passing.

| Category | Maximum | Certified | Evidence |
|---|---:|---:|---|
| Functionality | 25 | 24 | 32 deterministic tests; two immutable v2 capability profiles |
| Interface | 20 | 19 | Byte-pinned v1, strict v2 schema/OpenAPI, typed SDK and conformance |
| Reliability and safety | 20 | 18 | Product-limit rejection, bounded storage, concurrency and stop tests |
| Validation and performance | 15 | 13 | 9,053 cycles/s; 10,000-cycle allocation soak |
| Security and supply chain | 10 | 9 | Hardened local container, pinned base image, CI scanning and SBOM |
| Documentation and usability | 10 | 9 | v1/v2 I/O examples, target limits and hardware handoff procedure |
| **Total** | **100** | **92** | **Target met** |

## Hard gates

| Gate | Result | Evidence |
|---|---|---|
| Tests | Pass | pytest, Ruff and strict mypy |
| Runtime smoke | Pass | v2 digest/limit plus v1 lifecycle checks in `smoke.py` |
| Memory | Pass | 10,000 cycles, 128 retained records, 569,808-byte growth |
| Security | Pass | UID 65532, read-only root, all capabilities dropped, localhost port |
| Documentation examples | Pass | fresh-instance curl flow and typed client example |

`quality/check_score.py` verifies the shared scorecard schema and all five hard-gate
keys. `tools/check_quality.py` additionally verifies local evidence files and complete
requirements coverage. Scores must be updated only with evidence from the same commit.
