from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import psycopg


EXPECTED_ROWS = 472_550
EXPECTED_SYMBOLS = {"SPY", "QQQ"}
EXPECTED_DATES_PER_SYMBOL = 261
EXPECTED_EARLIEST_DATE = "2025-05-23"
EXPECTED_LATEST_DATE = "2026-08-27"

ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")
OUTPUT_DIR = ROOT / "data" / "second1m_archives"
OUTPUT_PATH = OUTPUT_DIR / "second1m_market_benchmark_adjusted_false_raw_v1.parquet"


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("SECOND 1M RAW BENCHMARK ARCHIVE")
    print("=" * 80)

    print("Connecting to Supabase...")

    conn = psycopg.connect(
        host=require_env("SUPABASE_DB_HOST"),
        port=5432,
        dbname="postgres",
        user=require_env("SUPABASE_DB_USER"),
        password=require_env("SUPABASE_DB_PASSWORD"),
        sslmode="require",
    )

    query = """
        select
            id,
            symbol,
            trade_date,
            timestamp_utc,
            timestamp_ms,
            timeframe,
            open,
            high,
            low,
            close,
            volume,
            vwap,
            transactions,
            data_source,
            adjusted,
            created_at
        from public.market_intraday_history
        where symbol in ('SPY', 'QQQ')
          and timeframe = '1m'
          and data_source = 'massive_1m'
          and adjusted = false
        order by symbol, timestamp_utc
    """

    print("Reading benchmark rows...")

    df = pd.read_sql_query(
        query,
        conn,
    )

    conn.close()

    if df.empty:
        raise RuntimeError("No adjusted=false SPY/QQQ rows found.")

    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)

    print()
    print("SOURCE VALIDATION")
    print("-" * 80)
    print(f"Rows:        {len(df):,}")
    print(f"Symbols:     {sorted(df['symbol'].unique())}")
    print(f"Earliest:    {df['trade_date'].min()}")
    print(f"Latest:      {df['trade_date'].max()}")

    if len(df) != EXPECTED_ROWS:
        raise RuntimeError(
            f"Row-count mismatch. Expected {EXPECTED_ROWS:,}, found {len(df):,}"
        )

    symbols = set(df["symbol"].unique())
    if symbols != EXPECTED_SYMBOLS:
        raise RuntimeError(
            f"Symbol mismatch. Expected {EXPECTED_SYMBOLS}, found {symbols}"
        )

    per_symbol = (
        df.groupby("symbol")["trade_date"]
        .nunique()
        .to_dict()
    )

    for symbol in EXPECTED_SYMBOLS:
        actual = int(per_symbol.get(symbol, 0))
        if actual != EXPECTED_DATES_PER_SYMBOL:
            raise RuntimeError(
                f"{symbol} date-count mismatch. "
                f"Expected {EXPECTED_DATES_PER_SYMBOL}, found {actual}"
            )

    earliest = str(df["trade_date"].min())
    latest = str(df["trade_date"].max())

    if earliest != EXPECTED_EARLIEST_DATE:
        raise RuntimeError(
            f"Earliest date mismatch. Expected {EXPECTED_EARLIEST_DATE}, found {earliest}"
        )

    if latest != EXPECTED_LATEST_DATE:
        raise RuntimeError(
            f"Latest date mismatch. Expected {EXPECTED_LATEST_DATE}, found {latest}"
        )

    duplicate_n = int(
        df.duplicated(
            ["symbol", "timestamp_utc", "timeframe", "data_source", "adjusted"]
        ).sum()
    )

    if duplicate_n != 0:
        raise RuntimeError(f"Duplicate canonical bars found: {duplicate_n}")

    if not (df["adjusted"] == False).all():
        raise RuntimeError("Archive contains adjusted=true rows.")

    if not (df["data_source"] == "massive_1m").all():
        raise RuntimeError("Unexpected data_source found.")

    if not (df["timeframe"] == "1m").all():
        raise RuntimeError("Unexpected timeframe found.")

    print(f"Duplicate bars: {duplicate_n}")
    print(f"SPY dates:      {per_symbol.get('SPY', 0)}")
    print(f"QQQ dates:      {per_symbol.get('QQQ', 0)}")

    temp_path = OUTPUT_PATH.with_suffix(".tmp.parquet")

    print()
    print(f"Writing archive: {OUTPUT_PATH}")

    df.to_parquet(
        temp_path,
        index=False,
    )

    print("Reading archive back for verification...")

    check = pd.read_parquet(temp_path)

    check["symbol"] = check["symbol"].astype(str).str.upper()
    check["trade_date"] = pd.to_datetime(check["trade_date"]).dt.date
    check["timestamp_utc"] = pd.to_datetime(check["timestamp_utc"], utc=True)

    if len(check) != len(df):
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Read-back row mismatch: wrote {len(df):,}, read {len(check):,}"
        )

    if set(check["symbol"].unique()) != EXPECTED_SYMBOLS:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError("Read-back symbol mismatch.")

    check_dates = (
        check.groupby("symbol")["trade_date"]
        .nunique()
        .to_dict()
    )

    for symbol in EXPECTED_SYMBOLS:
        if int(check_dates.get(symbol, 0)) != EXPECTED_DATES_PER_SYMBOL:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Read-back date-count mismatch for {symbol}"
            )

    if check["timestamp_utc"].nunique() != df["timestamp_utc"].nunique():
        temp_path.unlink(missing_ok=True)
        raise RuntimeError("Read-back timestamp uniqueness mismatch.")

    temp_path.replace(OUTPUT_PATH)

    print()
    print("=" * 80)
    print("ARCHIVE VERIFIED")
    print("=" * 80)
    print(f"Rows:        {len(check):,}")
    print(f"SPY dates:   {check_dates['SPY']}")
    print(f"QQQ dates:   {check_dates['QQQ']}")
    print(f"File size:   {OUTPUT_PATH.stat().st_size:,} bytes")
    print(f"Archive:     {OUTPUT_PATH}")
    print()
    print("RESULT: PASS")
    print("No database rows were deleted.")


if __name__ == "__main__":
    main()