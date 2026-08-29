from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from tr_platform.common.manifest import LocalManifest
from tr_platform.downloader.year_acquisition import acquire_symbol_year


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Production MARKET_CACHE_V1 symbol/year acquisition."
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload even if the exact year partition is already complete.",
    )
    args = parser.parse_args()

    result = acquire_symbol_year(
        symbol=args.symbol,
        year=args.year,
        force=args.force,
    )

    print()
    print("=== SYMBOL/YEAR ACQUISITION RESULT ===")
    print(f"Action:          {result.action}")
    print(f"Symbol:          {result.symbol}")
    print(f"Year:            {result.year}")
    print(f"Requested start: {result.requested_start}")
    print(f"Requested end:   {result.requested_end}")
    print(f"Rows:            {result.row_count:,}")
    print(f"Output:          {result.output_path}")
    print(f"Manifest:        {result.manifest_path}")

    if result.output_path.exists():
        df = pd.read_parquet(result.output_path)
        print()
        print("=== PARTITION READ-BACK ===")
        print(f"Rows:             {len(df):,}")
        print(f"Unique timestamps:{df['timestamp_utc'].nunique():,}")
        print(f"First ET:         {df['timestamp_et'].min()}")
        print(f"Last ET:          {df['timestamp_et'].max()}")
        print("Sessions:")
        print(df["session"].value_counts().to_string())

    manifest = LocalManifest(result.manifest_path)
    row = manifest.get(result.symbol, result.year)

    if row is not None:
        print()
        print("=== MANIFEST RECORD ===")
        for key in [
            "download_status",
            "validation_status",
            "download_attempts",
            "row_count",
            "trading_days",
            "rth_days",
            "premarket_days",
            "afterhours_days",
            "file_size_bytes",
            "file_hash",
        ]:
            print(f"{key}: {row.get(key)}")


if __name__ == "__main__":
    main()
