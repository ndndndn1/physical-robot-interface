# Capability-profile benchmark and leak acceptance

The v2 capability profile is immutable startup metadata. Command validation performs a
constant-time product lookup plus, for manipulation, a bounded scan of at most 16 joint
limits. No cache, worker, timer, model, or network call is added.

## Release commands and thresholds

```bash
uv run python tools/benchmark.py --iterations 2000 --min-cycles-per-second 2000
uv run python tools/soak.py --iterations 10000
```

The throughput gate requires at least 2,000 accepted command cycles per second. Each
cycle validates the MH-01 v2 speed limit, submits, advances the deterministic lifecycle,
and reports the profile digest used. The memory gate requires no more than 128 retained
commands and less than 8 MiB traced allocation growth after 10,000 MM-01 cycles. The
reported digest proves the run used a concrete capability profile.

The evidence recorded on 2026-09-02 is 9,053.42 cycles/s with 0.1191 ms p95.
The 10,000-cycle soak retained 128 commands and 569,808 bytes after collection, with
a 576,008-byte traced peak. The complete machine-readable result and exact profile
digests are in `quality/benchmark-evidence.json`.

These host-local numbers are regression evidence for the mock contract, not robot or
network latency claims. A real adapter needs a separate 30-minute RSS, thread, file
descriptor, reconnect, deadline, and HIL run before approval.
