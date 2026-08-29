# 8H-6A-5B — Massive 1-Minute Smoke Test

Copy these files into the existing `TradingResearch` repository.

## Files

- `platform/common/cache_config.py`
- `platform/downloader/massive_client.py`
- `platform/downloader/smoke_test_1d.py`

## Run from repository root

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run a one-day smoke test:

```powershell
python -m platform.downloader.smoke_test_1d --symbol AAPL --date 2026-08-27
```

To also write an ignored Parquet smoke-test file:

```powershell
python -m platform.downloader.smoke_test_1d --symbol AAPL --date 2026-08-27 --write
```

Expected file location:

`market_cache\MARKET_CACHE_V1\smoke_tests\AAPL_2026-08-27_1m.parquet`

This smoke test does not update Supabase or bulk-download the 112-stock universe.
