from __future__ import annotations

from tr_platform.historical.multi_symbol_smoke import (
    DEFAULT_SAMPLE,
    run_multi_symbol_smoke,
    write_smoke_report,
)


def main() -> None:
    summary = run_multi_symbol_smoke()
    report = write_smoke_report(summary)

    print("=== MULTI-SYMBOL HISTORICAL ENGINE SMOKE TEST ===")
    print(f"Sample size: {summary.total}")
    print(f"PASS:        {summary.passed}")
    print(f"FAIL:        {summary.failed}")
    print()

    for r in summary.results:
        print(
            f"{r.symbol} {r.year}: {r.status} | "
            f"rows={r.rows:,} | trading_days={r.trading_days} | "
            f"RTH/PRE/AH={r.rth_rows:,}/{r.pre_rows:,}/{r.ah_rows:,} | "
            f"cert={r.certification_status} | "
            f"manifest={r.manifest_validation_status} | "
            f"sha256_len={r.sha256_length}"
        )

    print()
    print(f"Report: {report}")

    if summary.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
