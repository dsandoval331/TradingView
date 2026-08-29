from __future__ import annotations

import argparse
import pandas as pd
from pathlib import Path

from tr_platform.validation.dataset_integrity import audit_universe_year


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit full PMPD_112_V1 MARKET_CACHE_V1 dataset integrity."
    )
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    summary = audit_universe_year(year=args.year)

    print("=== PMPD_112_V1 DATASET INTEGRITY AUDIT ===")
    print(f"Year:                 {summary.year}")
    print(f"Expected partitions:  {summary.expected_partitions}")
    print(f"Audited partitions:   {summary.audited_partitions}")
    print(f"PASS:                  {summary.pass_count}")
    print(f"WARN:                  {summary.warn_count}")
    print(f"FAIL:                  {summary.fail_count}")
    print(f"Research-ready cand.: {summary.research_ready_candidate}")
    print(f"CSV report:            {summary.report_csv}")
    print(f"Parquet report:        {summary.report_parquet}")

    if summary.fail_count:
        df = pd.read_csv(summary.report_csv)
        failed = df[df["status"] == "FAIL"][
            ["symbol", "status", "issues"]
        ]
        print()
        print("=== FAILED PARTITIONS ===")
        print(failed.to_string(index=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
