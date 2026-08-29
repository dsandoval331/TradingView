# 8H-6A-6D — Controlled Multi-Partition Acquisition

This package adds batch orchestration around the proven production
symbol/year downloader.

## Files

- `tr_platform/downloader/batch_acquisition.py`
- `tr_platform/downloader/run_controlled_batch.py`
- `tests/test_batch_summary.py`

## Step 1 — deterministic test

Run:

```powershell
python -m tests.test_batch_summary
```

Expected:

```text
=== BATCH SUMMARY LOGIC TEST PASS ===
Total: 3
Downloaded: 2
Skipped complete: 1
Failed: 0
```

## Step 2 — controlled live batch

Run:

```powershell
python -m tr_platform.downloader.run_controlled_batch
```

Enter your Massive API key once for the batch.

Expected first-run behavior:

- AAPL 2025 -> `SKIPPED_COMPLETE`
- MSFT 2025 -> `DOWNLOADED`
- NVDA 2025 -> `DOWNLOADED`

The free Massive plan may make the two new full-year downloads take several minutes.

## Step 3 — repeat batch

Run the same command again.

Expected second-run behavior:

- AAPL 2025 -> `SKIPPED_COMPLETE`
- MSFT 2025 -> `SKIPPED_COMPLETE`
- NVDA 2025 -> `SKIPPED_COMPLETE`

This proves multi-partition resume/skip behavior before moving toward the
112-stock acquisition universe.
