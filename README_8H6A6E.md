# 8H-6A-6E — Acquisition Hardening

This package replaces the 8H-6A-6D `batch_acquisition.py` with a hardened
version.

## Improvements

1. **Lazy Massive API-key prompt**
   - If every requested production partition is already complete, the batch
     never asks for the API key.
   - In a mixed batch, it prompts only when the first real download is needed.
   - One key is reused for all downloads in that batch.

2. **Failure isolation**
   - One failed partition can be recorded as failed while later partitions
     continue.
   - Completed partitions remain untouched.

3. **Test hooks**
   - Deterministic tests validate behavior without making API calls.

## Files

- `tr_platform/downloader/batch_acquisition.py` — replaces prior version
- `tests/test_acquisition_hardening.py`
- `tests/test_live_no_prompt_skip.py`

## Step 1 — deterministic hardening tests

```powershell
python -m tests.test_acquisition_hardening
```

Expected ending:

```text
All-complete batch / no API-key prompt: PASS
Mixed batch / prompt once: PASS
Failure isolation / continue batch: PASS

=== ACQUISITION HARDENING TEST PASS ===
```

## Step 2 — live no-prompt validation

Because AAPL/MSFT/NVDA 2025 are already complete:

```powershell
python -m tests.test_live_no_prompt_skip
```

You should NOT be prompted for the Massive API key.

Expected ending:

```text
Total:             3
Downloaded:        0
Skipped complete:  3
Failed:            0

=== LIVE NO-PROMPT SKIP TEST PASS ===
```
