from __future__ import annotations

import argparse
import pandas as pd

from tr_platform.validation.coverage_quality import audit_universe_coverage


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit PMPD_112_V1 market-data coverage quality."
    )
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    summary = audit_universe_coverage(year=args.year)

    print("=== PMPD_112_V1 COVERAGE QUALITY AUDIT ===")
    print(f"Year:                  {summary.year}")
    print(f"Expected partitions:   {summary.expected_partitions}")
    print(f"Audited partitions:    {summary.audited_partitions}")
    print(f"PASS:                   {summary.pass_count}")
    print(f"WARN:                   {summary.warn_count}")
    print(f"FAIL:                   {summary.fail_count}")
    print(f"Min RTH days:           {summary.min_trading_days}")
    print(f"Median RTH days:        {summary.median_trading_days}")
    print(f"Max RTH days:           {summary.max_trading_days}")
    print(f"Research-ready cand.:  {summary.research_ready_candidate}")
    print(f"CSV report:             {summary.report_csv}")
    print(f"Parquet report:         {summary.report_parquet}")

    df = pd.read_csv(summary.report_csv)
    attention = df[df["status"] != "PASS"]

    if not attention.empty:
        print()
        print("=== PARTITIONS REQUIRING REVIEW ===")
        cols = [
            "symbol", "status", "trading_days", "rth_days",
            "rth_days_below_300", "days_with_rth_gap_gt_15m",
            "max_rth_gap_minutes", "issues",
        ]
        print(attention[cols].to_string(index=False))

    if summary.fail_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
