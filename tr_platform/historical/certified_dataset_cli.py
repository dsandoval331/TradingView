from __future__ import annotations

import argparse

from tr_platform.historical.certified_dataset import load_certified_partition


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load one certified PMPD_112_V1 historical partition."
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Skip SHA-256 recomputation (manifest hash still required).",
    )
    args = parser.parse_args()

    p = load_certified_partition(
        symbol=args.symbol,
        year=args.year,
        verify_hash=not args.no_hash,
    )

    print("=== CERTIFIED DATASET LOADER PASS ===")
    print(f"Symbol:                 {p.symbol}")
    print(f"Year:                   {p.year}")
    print(f"Universe:               {p.universe_code}")
    print(f"Cache version:          {p.cache_version}")
    print(f"Timeframe:              {p.timeframe}")
    print(f"Source:                 {p.source}")
    print(f"Rows:                   {p.row_count:,}")
    print(f"First UTC:              {p.first_timestamp_utc}")
    print(f"Last UTC:               {p.last_timestamp_utc}")
    print(f"Manifest validation:    {p.manifest_validation_status}")
    print(f"Certification:          {p.certification_status}")
    print(f"SHA-256:                {p.file_sha256}")
    print()
    print("Session counts:")
    print(p.dataframe["session"].value_counts().to_string())
    print()
    print("Dtypes:")
    print(p.dataframe.dtypes.to_string())


if __name__ == "__main__":
    main()
