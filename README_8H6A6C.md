# 8H-6A-6C — Production Symbol/Year Acquisition

This package introduces the first production-capable `MARKET_CACHE_V1`
symbol/year downloader.

## Files

- `tr_platform/downloader/year_acquisition.py`
- `tr_platform/downloader/acquire_year_cli.py`
- `tests/test_year_bounds.py`

## Step 1 — Run deterministic test

From the repo root with `.venv` active:

```powershell
python -m tests.test_year_bounds
```

Expected:

```text
=== YEAR BOUNDS TEST PASS ===
2025 -> 2025-01-01 through 2025-12-31
2026 -> 2026-01-01 through 2026-08-28
Future year rejection: PASS
```

## Step 2 — Production-style one-symbol / one-year test

Recommended first year:

```powershell
python -m tr_platform.downloader.acquire_year_cli --symbol AAPL --year 2025
```

This is a real production cache write:

`market_cache\MARKET_CACHE_V1\1m\AAPL\2025.parquet`

and updates:

`market_cache\MARKET_CACHE_V1\manifests\market_cache_manifest.parquet`

The download may take several minutes because the Massive free plan is
rate-limited and the endpoint may paginate through many 1-minute bars.

## Step 3 — Resume/skip test

After the first run succeeds, run the exact same command again:

```powershell
python -m tr_platform.downloader.acquire_year_cli --symbol AAPL --year 2025
```

The second run should return:

`Action: SKIPPED_COMPLETE`

and should not prompt for the Massive API key.

## Important

Do not start the full 112-stock bootstrap yet.

This step only proves one real symbol/year production partition.
