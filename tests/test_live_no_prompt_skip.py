from __future__ import annotations

from tr_platform.downloader.batch_acquisition import acquire_batch, print_batch_summary


def main() -> None:
    # All three production partitions should already be complete from 8H-6A-6D.
    # The hardened batch MUST NOT ask for the Massive API key.
    items = [
        ("AAPL", 2025),
        ("MSFT", 2025),
        ("NVDA", 2025),
    ]

    summary = acquire_batch(items)
    print_batch_summary(summary)

    assert summary.total == 3
    assert summary.downloaded == 0
    assert summary.skipped_complete == 3
    assert summary.failed == 0

    print()
    print("=== LIVE NO-PROMPT SKIP TEST PASS ===")


if __name__ == "__main__":
    main()
