from pathlib import Path

from tr_platform.historical.multi_symbol_smoke import (
    DEFAULT_SAMPLE,
    run_multi_symbol_smoke,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    summary = run_multi_symbol_smoke(
        sample=DEFAULT_SAMPLE,
        repo_root=root,
        verify_hash=True,
    )

    assert summary.total == 6
    assert summary.failed == 0
    assert summary.passed == 6

    symbols = [r.symbol for r in summary.results]
    assert symbols == ["AAPL", "SPY", "JNJ", "PANW", "BKNG", "ARM"]

    for r in summary.results:
        assert r.status == "PASS"
        assert r.rows > 0
        assert r.trading_days == 250
        assert r.certification_status == "RESEARCH_READY"
        assert r.manifest_validation_status in {"PASS", "PASS_WITH_WARNINGS"}
        assert r.sha256_length == 64

    print("=== MULTI-SYMBOL ENGINE SMOKE TEST PASS ===")
    print("Symbols:", ", ".join(symbols))
    print("Sets represented: 1, 2, 3, 4")
    print("Includes dense control: SPY")
    print("Includes source-sparse case: BKNG")
    print("PASS: 6")
    print("FAIL: 0")


if __name__ == "__main__":
    main()
