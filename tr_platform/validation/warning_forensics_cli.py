from __future__ import annotations

import argparse
import pandas as pd

from tr_platform.validation.warning_forensics import (
    DEFAULT_SYMBOLS,
    run_warning_forensics,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Forensic review of PMPD coverage-audit warning symbols."
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--symbols",
        nargs="*",
        default=DEFAULT_SYMBOLS,
        help="Symbols to inspect. Defaults to the eight 2025 warning symbols.",
    )
    args = parser.parse_args()

    detail_csv, detail_parquet, summary_csv = run_warning_forensics(
        year=args.year,
        symbols=args.symbols,
    )

    summary = pd.read_csv(summary_csv)

    print("=== PMPD COVERAGE WARNING FORENSICS ===")
    print(f"Year: {args.year}")
    print(f"Symbols: {', '.join(args.symbols)}")
    print()
    print(summary.to_string(index=False))
    print()
    print(f"Daily detail CSV: {detail_csv}")
    print(f"Daily detail Parquet: {detail_parquet}")
    print(f"Summary CSV: {summary_csv}")

    if "BKNG" in set(summary["symbol"]):
        row = summary[summary["symbol"] == "BKNG"].iloc[0]
        print()
        print("=== BKNG FOCUS ===")
        print(f"RTH days: {int(row['rth_days'])}")
        print(f"Median RTH rows: {row['median_rth_rows']}")
        print(f"Days <300 rows: {int(row['days_lt300'])}")
        print(f"Days gap >15m: {int(row['days_gap_gt15m'])}")
        print(f"Days gap >30m: {int(row['days_gap_gt30m'])}")
        print(f"Max gap: {row['max_gap_minutes']} minutes")
        print(f"Worst date: {row['worst_gap_date']}")
        print(f"Worst gap: {row['worst_gap_start_et']} -> {row['worst_gap_end_et']}")


if __name__ == "__main__":
    main()
