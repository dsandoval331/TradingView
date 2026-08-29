from __future__ import annotations

from pathlib import Path

from tr_platform.universe.acquire_set import build_set_year_plan


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    summary = build_set_year_plan(
        set_number=1,
        year=2025,
        repo_root_path=root,
    )

    assert summary.total == 28
    assert summary.complete >= 3
    assert summary.needs_download == summary.total - summary.complete

    symbols = [i.symbol for i in summary.items]
    assert symbols[0] == "MSFT"
    assert symbols[6] == "AAPL"
    assert symbols[15] == "NVDA"
    assert symbols[-1] == "TQQQ"

    statuses = {i.symbol: i.status for i in summary.items}
    assert statuses["AAPL"] == "COMPLETE"
    assert statuses["MSFT"] == "COMPLETE"
    assert statuses["NVDA"] == "COMPLETE"

    print("=== UNIVERSE → ACQUISITION PLAN TEST PASS ===")
    print(f"Total: {summary.total}")
    print(f"Complete: {summary.complete}")
    print(f"Need download: {summary.needs_download}")
    print("Known production partitions:")
    print(f"AAPL 2025: {statuses['AAPL']}")
    print(f"MSFT 2025: {statuses['MSFT']}")
    print(f"NVDA 2025: {statuses['NVDA']}")


if __name__ == "__main__":
    main()
