# 8H-6A-6A — Local Manifest Engine

This package adds the local manifest layer for `MARKET_CACHE_V1`.

## Files

- `tr_platform/common/manifest.py`
- `tests/test_manifest_smoke.py`

## Purpose

The manifest tracks one row per canonical cache partition:

`symbol × year × timeframe × source × adjusted × cache_version`

It supports:

- insert/update partition state
- `DOWNLOADED` / `PARTIAL` / `FAILED`
- `PASS` / `PASS_WITH_WARNINGS` / `FAIL`
- file path, size, and SHA-256 hash
- atomic Parquet manifest writes
- complete-partition checks
- finding the next incomplete symbol/year

## Install

No new package is required beyond the existing environment.

## Test

From the repository root with `.venv` active:

```powershell
python tests\test_manifest_smoke.py
```

Expected output includes:

```text
=== MANIFEST SMOKE TEST PASS ===
AAPL 2026 complete: True
Next incomplete: ('MSFT', 2026)
SHA256 length: 64
```

The generated test files live under `market_cache`, which is already ignored by Git.
