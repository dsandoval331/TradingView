from __future__ import annotations

from tr_platform.downloader.batch_acquisition import (
    acquire_batch,
    print_batch_summary,
)


def main() -> None:
    # Controlled 8H-6A-6D production-style batch.
    #
    # Expected on first run:
    #   AAPL 2025 -> SKIPPED_COMPLETE
    #   MSFT 2025 -> DOWNLOADED
    #   NVDA 2025 -> DOWNLOADED
    #
    # Expected on second run:
    #   all three -> SKIPPED_COMPLETE
    items = [
        ("AAPL", 2025),
        ("MSFT", 2025),
        ("NVDA", 2025),
    ]

    summary = acquire_batch(items)
    print_batch_summary(summary)

    if summary.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
