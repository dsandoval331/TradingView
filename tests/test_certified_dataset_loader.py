from pathlib import Path

from tr_platform.historical.certified_dataset import load_certified_partition


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    aapl = load_certified_partition(
        symbol="AAPL",
        year=2025,
        repo_root=root,
        verify_hash=True,
    )

    assert aapl.symbol == "AAPL"
    assert aapl.year == 2025
    assert aapl.universe_code == "PMPD_112_V1"
    assert aapl.cache_version == "MARKET_CACHE_V1"
    assert aapl.timeframe == "1m"
    assert aapl.source == "massive"
    assert aapl.row_count > 0
    assert len(aapl.file_sha256) == 64
    assert aapl.certification_status == "RESEARCH_READY"

    print("=== CERTIFIED DATASET LOADER TEST PASS ===")
    print(f"AAPL 2025 rows: {aapl.row_count}")
    print(f"SHA256 length: {len(aapl.file_sha256)}")
    print(f"Certification: {aapl.certification_status}")


if __name__ == "__main__":
    main()
