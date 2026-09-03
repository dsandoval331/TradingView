from __future__ import annotations

import json
from pathlib import Path
from collections import Counter

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")
CACHE_ROOT = ROOT / "data" / "second1m_alt_entry_cache_v1"
MANIFEST_PATH = CACHE_ROOT / "manifests" / "alt_entry_manifest.json"

EXPECTED_SYMBOLS = 112
EXPECTED_PARTITIONS = 224


def main():
    print("=" * 80)
    print("SECOND 1M ALTERNATIVE C2 — FULL CACHE INTEGRITY")
    print("=" * 80)

    if not MANIFEST_PATH.exists():
        raise RuntimeError(f"Manifest not found: {MANIFEST_PATH}")

    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    parquet_files = sorted(CACHE_ROOT.rglob("*.parquet"))

    print(f"Manifest:       {MANIFEST_PATH}")
    print(f"Parquet files:  {len(parquet_files):,}")

    if len(parquet_files) != EXPECTED_PARTITIONS:
        print(
            f"WARNING: expected {EXPECTED_PARTITIONS} parquet partitions, "
            f"found {len(parquet_files)}"
        )

    total_rows = 0
    symbols = set()
    trade_dates = set()
    symbol_days = set()

    duplicate_key_n = 0

    missing_0930 = 0
    missing_0931 = 0
    missing_0932 = 0
    complete_c1_c2 = 0
    complete_c1_c2_c3 = 0

    symbol_day_counts = Counter()
    warning_files = []

    earliest = None
    latest = None

    for i, path in enumerate(parquet_files, start=1):

        table = pq.read_table(
            path,
            columns=[
                "symbol",
                "trade_date",
                "timestamp_utc",
            ],
        )

        df = table.to_pandas()

        if df.empty:
            warning_files.append((str(path), "EMPTY"))
            continue

        df["symbol"] = df["symbol"].astype(str).str.upper()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        df["timestamp_utc"] = pd.to_datetime(
            df["timestamp_utc"],
            utc=True,
        )

        total_rows += len(df)

        file_symbols = set(df["symbol"].unique())
        symbols.update(file_symbols)

        dates = set(df["trade_date"].unique())
        trade_dates.update(dates)

        for symbol, trade_date in (
            df[["symbol", "trade_date"]]
            .drop_duplicates()
            .itertuples(index=False, name=None)
        ):
            symbol_days.add((symbol, trade_date))
            symbol_day_counts[symbol] += 1

        file_earliest = df["trade_date"].min()
        file_latest = df["trade_date"].max()

        earliest = (
            file_earliest
            if earliest is None
            else min(earliest, file_earliest)
        )

        latest = (
            file_latest
            if latest is None
            else max(latest, file_latest)
        )

        duplicate_key_n += int(
            df.duplicated(
                ["symbol", "timestamp_utc"]
            ).sum()
        )

        et = df["timestamp_utc"].dt.tz_convert(
            "America/New_York"
        )

        df["_time_et"] = et.dt.strftime("%H:%M")

        opening = df[
            df["_time_et"].isin(
                ["09:30", "09:31", "09:32"]
            )
        ]

        opening_presence = (
            opening.assign(present=1)
            .pivot_table(
                index=["symbol", "trade_date"],
                columns="_time_et",
                values="present",
                aggfunc="max",
                fill_value=0,
            )
        )

        all_days = (
            df[["symbol", "trade_date"]]
            .drop_duplicates()
            .set_index(["symbol", "trade_date"])
        )

        opening_presence = all_days.join(
            opening_presence,
            how="left",
        ).fillna(0)

        for col in ["09:30", "09:31", "09:32"]:
            if col not in opening_presence.columns:
                opening_presence[col] = 0

        c1 = opening_presence["09:30"] == 1
        c2 = opening_presence["09:31"] == 1
        c3 = opening_presence["09:32"] == 1

        missing_0930 += int((~c1).sum())
        missing_0931 += int((~c2).sum())
        missing_0932 += int((~c3).sum())

        complete_c1_c2 += int((c1 & c2).sum())
        complete_c1_c2_c3 += int((c1 & c2 & c3).sum())

        if i % 20 == 0 or i == len(parquet_files):
            print(
                f"Processed {i:>3}/{len(parquet_files)} "
                f"| rows={total_rows:,} "
                f"| symbol-days={len(symbol_days):,}"
            )

    print()
    print("=" * 80)
    print("CACHE SUMMARY")
    print("=" * 80)

    print(f"Rows:                    {total_rows:,}")
    print(f"Symbols:                 {len(symbols):,}")
    print(f"Partitions:              {len(parquet_files):,}")
    print(f"Distinct trading dates:  {len(trade_dates):,}")
    print(f"Symbol-days:             {len(symbol_days):,}")
    print(f"Earliest date:           {earliest}")
    print(f"Latest date:             {latest}")
    print(f"Duplicate symbol/time:   {duplicate_key_n:,}")

    print()
    print("OPENING SEQUENCE")
    print("-" * 80)

    print(f"Missing C1 / 09:30:      {missing_0930:,}")
    print(f"Missing C2 / 09:31:      {missing_0931:,}")
    print(f"Missing C3 / 09:32:      {missing_0932:,}")
    print(f"Complete C1+C2:          {complete_c1_c2:,}")
    print(f"Complete C1+C2+C3:       {complete_c1_c2_c3:,}")

    print()
    print("SYMBOL COVERAGE")
    print("-" * 80)

    counts = list(symbol_day_counts.values())

    if counts:
        print(f"Min days/symbol:         {min(counts):,}")
        print(f"Average days/symbol:     {sum(counts)/len(counts):,.2f}")
        print(f"Max days/symbol:         {max(counts):,}")

    print()
    print("LOWEST-COVERAGE SYMBOLS")
    print("-" * 80)

    for symbol, n in sorted(
        symbol_day_counts.items(),
        key=lambda x: (x[1], x[0]),
    )[:15]:
        print(f"{symbol:<8} {n:>5}")

    print()
    print("=" * 80)
    print("INTEGRITY GATE")
    print("=" * 80)

    hard_failures = []

    if len(symbols) != EXPECTED_SYMBOLS:
        hard_failures.append(
            f"Expected {EXPECTED_SYMBOLS} symbols, found {len(symbols)}"
        )

    if duplicate_key_n != 0:
        hard_failures.append(
            f"Found {duplicate_key_n:,} duplicate symbol/timestamp rows"
        )

    if hard_failures:
        print("RESULT: FAIL")
        for failure in hard_failures:
            print(f" - {failure}")
    else:
        print("RESULT: PASS")
        print(
            "The cache is structurally suitable for the next "
            "Alternative C2 research stage."
        )


if __name__ == "__main__":
    main()