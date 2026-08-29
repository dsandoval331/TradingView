from __future__ import annotations

from pathlib import Path

from tr_platform.downloader.batch_acquisition import acquire_batch
from tr_platform.downloader.year_acquisition import YearAcquisitionResult


def fake_result(symbol: str, year: int, action: str, rows: int) -> YearAcquisitionResult:
    return YearAcquisitionResult(
        action=action,
        symbol=symbol,
        year=year,
        requested_start=f"{year}-01-01",
        requested_end=f"{year}-12-31",
        row_count=rows,
        output_path=Path(f"{symbol}_{year}.parquet"),
        manifest_path=Path("manifest.parquet"),
    )


def test_all_complete_requires_no_api_key() -> None:
    prompt_calls = 0

    def checker(symbol: str, year: int) -> bool:
        return True

    def prompt(_: str) -> str:
        nonlocal prompt_calls
        prompt_calls += 1
        raise AssertionError("API key prompt should not occur for all-complete batch.")

    def acquire_func(**kwargs):
        return fake_result(kwargs["symbol"], kwargs["year"], "SKIPPED_COMPLETE", 100)

    summary = acquire_batch(
        [("AAPL", 2025), ("MSFT", 2025), ("NVDA", 2025)],
        completeness_checker=checker,
        acquire_func=acquire_func,
        api_key_prompt=prompt,
    )

    assert prompt_calls == 0
    assert summary.downloaded == 0
    assert summary.skipped_complete == 3
    assert summary.failed == 0


def test_prompt_once_for_multiple_downloads() -> None:
    prompt_calls = 0

    def checker(symbol: str, year: int) -> bool:
        return symbol == "AAPL"

    def prompt(_: str) -> str:
        nonlocal prompt_calls
        prompt_calls += 1
        return "TEST_KEY"

    def acquire_func(**kwargs):
        symbol = kwargs["symbol"]
        year = kwargs["year"]

        if symbol == "AAPL":
            assert kwargs["api_key"] is None
            return fake_result(symbol, year, "SKIPPED_COMPLETE", 100)

        assert kwargs["api_key"] == "TEST_KEY"
        return fake_result(symbol, year, "DOWNLOADED", 200)

    summary = acquire_batch(
        [("AAPL", 2025), ("MSFT", 2025), ("NVDA", 2025)],
        completeness_checker=checker,
        acquire_func=acquire_func,
        api_key_prompt=prompt,
    )

    assert prompt_calls == 1
    assert summary.downloaded == 2
    assert summary.skipped_complete == 1
    assert summary.failed == 0


def test_failure_isolation_continues_batch() -> None:
    def checker(symbol: str, year: int) -> bool:
        return False

    def prompt(_: str) -> str:
        return "TEST_KEY"

    def acquire_func(**kwargs):
        symbol = kwargs["symbol"]
        year = kwargs["year"]

        if symbol == "BAD":
            raise RuntimeError("simulated partition failure")

        return fake_result(symbol, year, "DOWNLOADED", 300)

    summary = acquire_batch(
        [("MSFT", 2025), ("BAD", 2025), ("NVDA", 2025)],
        completeness_checker=checker,
        acquire_func=acquire_func,
        api_key_prompt=prompt,
        continue_on_error=True,
    )

    assert summary.total == 3
    assert summary.downloaded == 2
    assert summary.skipped_complete == 0
    assert summary.failed == 1
    assert summary.results[1].symbol == "BAD"
    assert summary.results[1].action == "FAILED"
    assert "simulated partition failure" in (summary.results[1].error or "")


def main() -> None:
    test_all_complete_requires_no_api_key()
    print("All-complete batch / no API-key prompt: PASS")

    test_prompt_once_for_multiple_downloads()
    print("Mixed batch / prompt once: PASS")

    test_failure_isolation_continues_batch()
    print("Failure isolation / continue batch: PASS")

    print()
    print("=== ACQUISITION HARDENING TEST PASS ===")


if __name__ == "__main__":
    main()
