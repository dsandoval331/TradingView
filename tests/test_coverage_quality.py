from pathlib import Path
from tr_platform.validation.coverage_quality import audit_universe_coverage


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    s = audit_universe_coverage(year=2025, repo_root=root)
    assert s.expected_partitions == 112
    assert s.audited_partitions == 112
    print("=== COVERAGE QUALITY TEST COMPLETE ===")
    print(f"PASS: {s.pass_count}")
    print(f"WARN: {s.warn_count}")
    print(f"FAIL: {s.fail_count}")
    print(f"Min/Median/Max RTH days: {s.min_trading_days}/{s.median_trading_days}/{s.max_trading_days}")
    print(f"Research-ready candidate: {s.research_ready_candidate}")
    print(f"CSV: {s.report_csv}")


if __name__ == "__main__":
    main()
