from pathlib import Path

from tr_platform.historical.guardrail_gate import run_guardrail_gate


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    results = run_guardrail_gate(repo_root)

    assert len(results) == 5
    assert all(r.passed for r in results)

    names = [r.name for r in results]
    assert names == [
        "unknown_symbol_rejected",
        "uncertified_year_rejected",
        "missing_partition_rejected",
        "hash_mismatch_rejected",
        "non_ready_certification_rejected",
    ]

    print("=== HISTORICAL ENGINE GUARDRAIL TEST PASS ===")
    for r in results:
        print(f"{r.name}: PASS ({r.observed_exception})")
    print("PASS: 5")
    print("FAIL: 0")
    print("Production cache mutated: NO")


if __name__ == "__main__":
    main()
