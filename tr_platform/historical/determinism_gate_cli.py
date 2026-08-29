from __future__ import annotations

from tr_platform.historical.determinism_gate import (
    run_determinism_pass,
    compare_runs,
    write_determinism_report,
)


def main() -> None:
    print("=== HISTORICAL ENGINE DETERMINISM GATE ===")

    run1 = run_determinism_pass(run_number=1)
    run2 = run_determinism_pass(run_number=2)

    issues = compare_runs(run1, run2)
    report = write_determinism_report(run1, run2, issues)

    print(f"Run 1 aggregate SHA-256: {run1.aggregate_fingerprint_sha256}")
    print(f"Run 2 aggregate SHA-256: {run2.aggregate_fingerprint_sha256}")
    print()

    for p1, p2 in zip(run1.partition_fingerprints, run2.partition_fingerprints):
        status = "PASS" if p1.fingerprint_sha256 == p2.fingerprint_sha256 else "FAIL"
        print(
            f"{p1.symbol}: {status} | "
            f"{p1.fingerprint_sha256} | "
            f"rows={p1.row_count:,} | "
            f"days={p1.trading_days}"
        )

    print()
    print(f"Report: {report}")

    if issues:
        print("Determinism issues:")
        for issue in issues:
            print(f"- {issue}")
        raise SystemExit(1)

    print()
    print("=== DETERMINISM GATE PASS ===")


if __name__ == "__main__":
    main()
