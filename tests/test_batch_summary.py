from __future__ import annotations

from tr_platform.downloader.batch_acquisition import BatchItemResult, BatchRunSummary


def main() -> None:
    # Deterministic summary-shape test only; no API calls.
    results = [
        BatchItemResult("AAPL", 2025, "SKIPPED_COMPLETE", 188072, True),
        BatchItemResult("MSFT", 2025, "DOWNLOADED", 190000, True),
        BatchItemResult("NVDA", 2025, "DOWNLOADED", 200000, True),
    ]

    summary = BatchRunSummary(
        total=3,
        downloaded=2,
        skipped_complete=1,
        failed=0,
        results=results,
    )

    assert summary.total == 3
    assert summary.downloaded == 2
    assert summary.skipped_complete == 1
    assert summary.failed == 0

    print("=== BATCH SUMMARY LOGIC TEST PASS ===")
    print("Total: 3")
    print("Downloaded: 2")
    print("Skipped complete: 1")
    print("Failed: 0")


if __name__ == "__main__":
    main()
