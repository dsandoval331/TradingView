from __future__ import annotations

from getpass import getpass
from pathlib import Path
import argparse

import pandas as pd

from tr_platform.common.cache_config import (
    CACHE_VERSION,
    SOURCE_NAME,
    MarketCacheConfig,
    NEW_YORK_TZ,
    classify_session,
)
from tr_platform.downloader.massive_client import MassiveClient, MassiveClientConfig


def find_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def normalize_results(symbol: str, rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).copy()

    df = df.rename(columns={
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "vw": "vwap",
        "n": "transactions",
        "t": "timestamp_ms",
    })

    required = ["timestamp_ms", "open", "high", "low", "close", "volume"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Massive response missing required columns: {missing}")

    if "vwap" not in df.columns:
        df["vwap"] = pd.NA
    if "transactions" not in df.columns:
        df["transactions"] = pd.NA

    df["symbol"] = symbol.upper().strip()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)
    df["timestamp_et"] = df["timestamp_utc"].dt.tz_convert(NEW_YORK_TZ)
    df["trade_date"] = df["timestamp_et"].dt.date
    df["session"] = [classify_session(ts.hour, ts.minute) for ts in df["timestamp_et"]]

    df["source"] = SOURCE_NAME
    df["adjusted"] = False
    df["cache_version"] = CACHE_VERSION

    columns = [
        "symbol",
        "timestamp_utc",
        "timestamp_et",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
        "transactions",
        "timestamp_ms",
        "session",
        "source",
        "adjusted",
        "cache_version",
    ]

    df = df[columns].sort_values("timestamp_utc").reset_index(drop=True)

    duplicate_count = df.duplicated(subset=["symbol", "timestamp_utc"]).sum()
    if duplicate_count:
        raise ValueError(f"Duplicate symbol/timestamp rows found: {duplicate_count}")

    invalid_ohlc = (
        (df["high"] < df[["open", "close", "low"]].max(axis=1))
        | (df["low"] > df[["open", "close", "high"]].min(axis=1))
    ).sum()

    if invalid_ohlc:
        raise ValueError(f"Invalid OHLC rows found: {invalid_ohlc}")

    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-symbol / one-day Massive 1-minute smoke test."
    )
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write smoke-test output to ignored market_cache folder.",
    )
    args = parser.parse_args()

    api_key = getpass("Enter your Massive API key: ").strip()

    client = MassiveClient(
        MassiveClientConfig(
            api_key=api_key,
            requests_per_minute=4.0,
        )
    )

    print(f"Requesting {args.symbol.upper()} 1-minute bars for {args.date}...")
    rows = client.get_minute_aggs(
        symbol=args.symbol,
        start_date=args.date,
        end_date=args.date,
        adjusted=False,
    )

    df = normalize_results(args.symbol, rows)

    if df.empty:
        print("No bars returned.")
        return

    print()
    print("=== SMOKE TEST SUMMARY ===")
    print(f"Rows:            {len(df):,}")
    print(f"First ET bar:    {df['timestamp_et'].iloc[0]}")
    print(f"Last ET bar:     {df['timestamp_et'].iloc[-1]}")
    print(f"Adjusted:        {df['adjusted'].iloc[0]}")
    print(f"Cache version:   {df['cache_version'].iloc[0]}")
    print()
    print("Session counts:")
    print(df["session"].value_counts().to_string())
    print()
    print("First 5 canonical rows:")
    print(df.head(5).to_string(index=False))

    if args.write:
        repo_root = find_repo_root()
        cfg = MarketCacheConfig.from_repo_root(repo_root)
        cfg.ensure_directories()

        smoke_dir = cfg.cache_root / "smoke_tests"
        smoke_dir.mkdir(parents=True, exist_ok=True)

        output_path = smoke_dir / f"{args.symbol.upper()}_{args.date}_1m.parquet"
        df.to_parquet(output_path, index=False)

        print()
        print("Wrote smoke-test Parquet file:")
        print(output_path)


if __name__ == "__main__":
    main()
