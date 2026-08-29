from __future__ import annotations

from pathlib import Path
from tr_platform.validation.dataset_integrity import audit_universe_year


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    summary = audit_universe_year(year=2025, repo_root=root)

    assert summary.expected_partitions == 112
    assert summary.audited_partitions == 112

    print("=== DATASET INTEGRITY TEST COMPLETE ===")
    print(f"PASS: {summary.pass_count}")
    print(f"WARN: {summary.warn_count}")
    print(f"FAIL: {summary.fail_count}")
    print(f"Research-ready candidate: {summary.research_ready_candidate}")
    print(f"CSV: {summary.report_csv}")
    print(f"Parquet: {summary.report_parquet}")


if __name__ == "__main__":
    main()
