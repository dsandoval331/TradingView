# 8H-6A-6H-5 — Artifact & Provenance Gate

This gate proves that a historical research run can be traced back to its
strategy/model, frozen universe, certified dataset, source partitions, source
hashes, environment, Git commit, and run configuration.

The provenance artifact records:
- strategy code: PMPD
- model version: V4
- universe: PMPD_112_V1
- cache version / timeframe / source
- research year
- current Git commit (when available)
- Python / pandas / pyarrow versions
- frozen-universe migration path + SHA-256
- readiness-certification path + SHA-256
- parity-spec path + SHA-256 when found
- run configuration
- six certified sample partition paths, hashes, row counts, timestamps,
  certification and manifest status
- deterministic provenance fingerprint

`generated_at_utc` is deliberately excluded from the fingerprint, so rebuilding
the same provenance inputs/config produces the same fingerprint.

Run:
`python -m tests.test_historical_provenance`

Then:
`python -m tr_platform.historical.provenance_gate_cli`

The CLI writes JSON and human-readable text provenance artifacts under:
`strategies/pmpd/output/provenance/`
