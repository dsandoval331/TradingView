# 8H-6A-6G-1 — Full 2025 Dataset Integrity Audit

This package audits all 112 acquired PMPD_112_V1 / 2025 production partitions.

Checks include:
- manifest record exists
- production file exists
- manifest download/validation status
- manifest row count vs Parquet row count
- unique/duplicate timestamps
- OHLC structural validity
- symbol consistency
- cache version consistency
- source consistency
- adjusted flag consistency
- manifest file size vs actual file size
- SHA-256 file hash
- ET timestamp year containment

It does **not** yet judge market-data density or missing-minute quality. Those are
separate coverage/readiness checks and should not be conflated with file/schema
integrity.

## Files

- `tr_platform/validation/dataset_integrity.py`
- `tr_platform/validation/dataset_integrity_cli.py`
- `tests/test_dataset_integrity.py`

## Run

From the repo root:

```powershell
python -m tr_platform.validation.dataset_integrity_cli --year 2025
```

Expected ideal result:

```text
Expected partitions: 112
Audited partitions:  112
PASS:                112
WARN:                  0
FAIL:                  0
Research-ready cand.: True
```

Reports are written under the ignored `market_cache/MARKET_CACHE_V1/validation/`
directory.
