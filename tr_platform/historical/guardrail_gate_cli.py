from pathlib import Path

from tr_platform.historical.guardrail_gate import (
    run_guardrail_gate,
    write_guardrail_report,
)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    results = run_guardrail_gate(repo_root)
    report = write_guardrail_report(results, repo_root)

    print("=== HISTORICAL ENGINE FAILURE / GUARDRAIL GATE ===")

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print()
        print(f"{r.name}: {status}")
        print(f"  Expected: {r.expected_exception}")
        print(f"  Observed: {r.observed_exception}")
        print(f"  Message:  {r.message}")

    passed = sum(r.passed for r in results)
    failed = len(results) - passed

    print()
    print("=== GUARDRAIL SUMMARY ===")
    print(f"Cases: {len(results)}")
    print(f"PASS:  {passed}")
    print(f"FAIL:  {failed}")
    print(f"Report: {report}")

    if failed:
        raise SystemExit(1)

    print()
    print("=== FAILURE / GUARDRAIL GATE PASS ===")


if __name__ == "__main__":
    main()
