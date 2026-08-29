# 8H-6A-6H-3 — Reproducibility / Determinism Gate

This gate runs the same certified historical workload twice and verifies that
both runs produce identical partition-level and aggregate fingerprints.

Sample:
- AAPL
- SPY
- JNJ
- PANW
- BKNG
- ARM

Each partition fingerprint includes:
- row count
- first/last UTC timestamp
- source-file SHA-256
- PRE/RTH/AH row counts
- trading-day count
- deterministic close sum
- deterministic volume sum

An aggregate SHA-256 is then calculated from all six partition fingerprints.

Run:
`python -m tests.test_historical_engine_determinism`

Then:
`python -m tr_platform.historical.determinism_gate_cli`

A passing gate requires:
- all six partition fingerprints identical across runs
- aggregate fingerprints identical
- zero comparison issues

Read-only with respect to production cache/manifest.
