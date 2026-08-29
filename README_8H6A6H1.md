# 8H-6A-6H-1 — Certified Dataset Loader Gate

This package creates the production historical-data loading interface that
future PM+PD historical-engine work should use.

A partition is refused unless:
1. `PMPD_112_V1 × YEAR` has a readiness-certification CSV with
   `RESEARCH_READY / research_ready=true`.
2. The symbol is in the authoritative frozen `PMPD_112_V1` universe.
3. The production manifest says the partition is DOWNLOADED and validated.
4. The Parquet file exists.
5. Manifest and Parquet row counts agree.
6. SHA-256 agrees with the manifest.
7. Canonical schema, timezone-aware timestamps, numeric columns, source,
   cache version, adjusted flag, symbol, year, and session labels pass.

Files:
- `tr_platform/historical/certified_dataset.py`
- `tr_platform/historical/certified_dataset_cli.py`
- `tests/test_certified_dataset_loader.py`

Run deterministic/local gate:
`python -m tests.test_certified_dataset_loader`

Then inspect a production partition:
`python -m tr_platform.historical.certified_dataset_cli --symbol AAPL --year 2025`

Both commands are read-only.
