from __future__ import annotations

from datetime import date

from tr_platform.downloader.year_acquisition import _year_bounds


def main() -> None:
    # Deterministic logic test that does NOT call Massive.
    today = date(2026, 8, 28)

    assert _year_bounds(2025, today) == ("2025-01-01", "2025-12-31")
    assert _year_bounds(2026, today) == ("2026-01-01", "2026-08-28")

    try:
        _year_bounds(2027, today)
    except ValueError:
        pass
    else:
        raise AssertionError("Future year should raise ValueError.")

    print("=== YEAR BOUNDS TEST PASS ===")
    print("2025 -> 2025-01-01 through 2025-12-31")
    print("2026 -> 2026-01-01 through 2026-08-28")
    print("Future year rejection: PASS")


if __name__ == "__main__":
    main()
