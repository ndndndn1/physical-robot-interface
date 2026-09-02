# Enterprise requirements and benchmark definition

The scope is deliberately narrow: a trustworthy physical-robot contract, a useful mock,
and a replaceable adapter boundary. This project is not a robot motion planner, certified
safety controller, fleet database, or vendor driver.

| ID | Requirement | Acceptance evidence |
|---|---|---|
| FUNC-01 | Both named product profiles support navigation and manipulation | catalog and contract tests |
| FUNC-02 | Full command lifecycle, cancellation and deterministic execution | runtime tests |
| FUNC-03 | Same-ID idempotency and changed-payload conflict | runtime and API tests |
| FUNC-04 | MH-01 and MM-01 expose immutable v2 joint, force, speed, payload and frame capability profiles | contract, API and digest tests |
| SAFE-01 | Expired, stale, busy and E-stop-blocked motion fails closed | rejection tests |
| SAFE-02 | Software protective stop is never presented as hardware E-stop | separate fields, docs and tests |
| SAFE-03 | Mock rejects product-specific joint, force and navigation-speed violations before state changes | boundary and rejection tests |
| INTF-01 | Versioned strict JSON Schema, OpenAPI and typed client | generated contracts and SDK test |
| INTF-02 | RobotPort is directly implementable by later hardware adapters | protocol and harness |
| INTF-03 | `/v1` schema bytes remain compatible while `/v2/products` is strict and independently versioned | pinned schema hashes and generated OpenAPI |
| REL-01 | Stores and active work are bounded and cleaned without workers | capacity, cleanup and soak tests |
| REL-02 | Concurrent access does not corrupt state | lock-based runtime and concurrency test |
| PERF-01 | 2,000 command cycles/s minimum on the reference host | benchmark script result |
| PERF-02 | 10,000-cycle soak retains at most configured commands and grows under 8 MiB | soak script |
| SEC-01 | Container is non-root, read-only, capability-free and localhost-published | Docker config inspection/smoke |
| DOC-01 | Customer can run mock, SDK, conformance, and hardware handoff | README and focused guides |

The machine-readable source is `quality/requirements.json`. Scores use the following
fixed weights: functionality 25, interface 20, reliability and safety 20, validation
and performance 15, security and supply chain 10, documentation and usability 10.
A score below 80 blocks release. `tools/check_quality.py` fails when weights, evidence,
coverage, or the threshold are invalid.

Performance benchmarks run after a warm-up with a fixed clock and bounded capacity.
They do not measure hardware latency. The soak uses Python allocation deltas as a
repeatable leak signal; production adapters additionally require transport-specific
long-duration RSS and descriptor monitoring.

The benchmark executes the same profile-limit checks used by ordinary accepted command
cycles and reports the immutable profile digest. The soak retains only the configured
128 terminal commands and reads a single immutable profile; no model, perception,
dataset, hardware, or background-worker lifecycle is introduced.
