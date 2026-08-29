# 8H-6A-6B — Manifest + Massive Downloader Integration

Recommended repo contents:

- `tr_platform/downloader/partition_acquisition.py`
- `tests/test_acquisition_integration.py`

Run from the repository root with `.venv` active:

```powershell
python -m tests.test_acquisition_integration
```

Expected behavior:

1. First pass asks for the Massive API key.
2. AAPL 2026-08-27 is downloaded and validated.
3. Parquet is written atomically.
4. SHA-256 and status are recorded in a dedicated test manifest.
5. Second pass recognizes the exact completed range and skips it.
6. The second pass should NOT ask for the API key.

Expected ending:

```text
First action: DOWNLOADED
Rows: 860
Second action: SKIPPED_COMPLETE
=== MANIFEST + MASSIVE INTEGRATION PASS ===
Manifest download status: DOWNLOADED
Manifest validation status: PASS
SHA256 length: 64
Resume/skip behavior: PASS
```

This uses a dedicated integration-test cache version and does not mark a full
production symbol/year partition complete.
