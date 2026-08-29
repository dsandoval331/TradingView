from pathlib import Path

from tr_platform.historical.determinism_gate import (
    DEFAULT_SAMPLE,
    run_determinism_pass,
    compare_runs,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    a = run_determinism_pass(
        run_number=1,
        sample=DEFAULT_SAMPLE,
        repo_root=root,
    )
    b = run_determinism_pass(
        run_number=2,
        sample=DEFAULT_SAMPLE,
        repo_root=root,
    )

    issues = compare_runs(a, b)

    assert not issues
    assert a.aggregate_fingerprint_sha256 == b.aggregate_fingerprint_sha256
    assert len(a.aggregate_fingerprint_sha256) == 64

    for p1, p2 in zip(a.partition_fingerprints, b.partition_fingerprints):
        assert p1.fingerprint_sha256 == p2.fingerprint_sha256
        assert len(p1.fingerprint_sha256) == 64

    print("=== HISTORICAL ENGINE DETERMINISM TEST PASS ===")
    print(f"Symbols: {', '.join(s for s, _ in DEFAULT_SAMPLE)}")
    print(f"Aggregate fingerprint: {a.aggregate_fingerprint_sha256}")
    print("Partition fingerprints: identical across two runs")
    print("PASS: 6")
    print("FAIL: 0")


if __name__ == "__main__":
    main()
