from pathlib import Path

from tr_platform.validation.warning_forensics import (
    DEFAULT_SYMBOLS,
    run_warning_forensics,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    detail_csv, detail_parquet, summary_csv = run_warning_forensics(
        year=2025,
        symbols=DEFAULT_SYMBOLS,
        repo_root=root,
    )

    assert detail_csv.exists()
    assert detail_parquet.exists()
    assert summary_csv.exists()

    print("=== WARNING FORENSICS TEST COMPLETE ===")
    print(f"Symbols: {len(DEFAULT_SYMBOLS)}")
    print(f"Summary: {summary_csv}")


if __name__ == "__main__":
    main()
