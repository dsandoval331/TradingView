from __future__ import annotations

from pathlib import Path

import pandas as pd

from tr_platform.common.manifest import LocalManifest
from tr_platform.downloader.partition_acquisition import acquire_date_range


TEST_CACHE_VERSION = "MARKET_CACHE_V1_INTEGRATION_TEST"


def main() -> None:
    root = Path("market_cache") / "MARKET_CACHE_V1" / "integration_tests"
    root.mkdir(parents=True, exist_ok=True)

    output_path = root / "AAPL_2026-08-27_1m.parquet"
    manifest_path = root / "integration_manifest.parquet"

    # Reset this controlled integration test.
    output_path.unlink(missing_ok=True)
    manifest_path.unlink(missing_ok=True)

    print("=== 8H-6A-6B INTEGRATION TEST ===")
    print("First pass should DOWNLOAD and will request your Massive API key.")
    print()

    first = acquire_date_range(
        symbol="AAPL",
        requested_start="2026-08-27",
        requested_end="2026-08-27",
        output_path=output_path,
        manifest_path=manifest_path,
        cache_version=TEST_CACHE_VERSION,
    )

    print(f"First action: {first.action}")
    print(f"Rows: {first.row_count}")

    df = pd.read_parquet(output_path)
    manifest = LocalManifest(manifest_path)
    row = manifest.get(
        symbol="AAPL",
        year=2026,
        adjusted=False,
        cache_version=TEST_CACHE_VERSION,
    )

    assert first.action == "DOWNLOADED"
    assert len(df) == 860
    assert df["timestamp_utc"].nunique() == 860
    assert int((df["session"] == "RTH").sum()) == 390
    assert row is not None
    assert row["download_status"] == "DOWNLOADED"
    assert row["validation_status"] == "PASS"
    assert len(str(row["file_hash"])) == 64

    print()
    print("Second pass should SKIP without asking for the API key.")

    second = acquire_date_range(
        symbol="AAPL",
        requested_start="2026-08-27",
        requested_end="2026-08-27",
        output_path=output_path,
        manifest_path=manifest_path,
        cache_version=TEST_CACHE_VERSION,
    )

    assert second.action == "SKIPPED_COMPLETE"

    print(f"Second action: {second.action}")
    print()
    print("=== MANIFEST + MASSIVE INTEGRATION PASS ===")
    print(f"Manifest download status: {row['download_status']}")
    print(f"Manifest validation status: {row['validation_status']}")
    print(f"SHA256 length: {len(str(row['file_hash']))}")
    print("Resume/skip behavior: PASS")


if __name__ == "__main__":
    main()
