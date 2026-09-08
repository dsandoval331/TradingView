from __future__ import annotations

import argparse

from tr_platform.downloader.batch_acquisition import (
    acquire_batch,
    print_batch_summary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a controlled MARKET_CACHE_V1 batch acquisition."
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="One or more ticker symbols, e.g. SPY QQQ DIA XLE XLK",
    )

    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Calendar year to acquire.",
    )

    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately if any symbol fails.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    items = [
        (symbol.upper().strip(), args.year)
        for symbol in args.symbols
    ]

    summary = acquire_batch(
        items,
        continue_on_error=not args.stop_on_error,
    )

    print_batch_summary(summary)

    if summary.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
