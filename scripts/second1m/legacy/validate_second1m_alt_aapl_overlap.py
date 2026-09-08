from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import psycopg


# ============================================================
# CONFIG
# ============================================================

SYMBOL = "AAPL"

CACHE_ROOT = Path(
    r"C:\Users\DirtySouth\TradingResearch\data\second1m_alt_entry_cache_v1\partitions"
)

PARQUET_FILES = [
    CACHE_ROOT / SYMBOL / f"{SYMBOL}_2025.parquet",
    CACHE_ROOT / SYMBOL / f"{SYMBOL}_2026.parquet",
]

PRICE_TOLERANCE = 1e-8
VWAP_TOLERANCE = 1e-8
VOLUME_TOLERANCE = 1e-8


# ============================================================
# ENVIRONMENT
# ============================================================

required_env = [
    "SUPABASE_DB_HOST",
    "SUPABASE_DB_USER",
    "SUPABASE_DB_PASSWORD",
]

missing = [
    name
    for name in required_env
    if not os.environ.get(name)
]

if missing:
    raise RuntimeError(
        "Missing environment variables: "
        + ", ".join(missing)
    )


# ============================================================
# LOAD LOCAL CACHE
# ============================================================

for path in PARQUET_FILES:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing cache partition: {path}"
        )

local = pd.concat(
    [
        pd.read_parquet(path)
        for path in PARQUET_FILES
    ],
    ignore_index=True,
)

local["symbol"] = (
    local["symbol"]
    .astype(str)
    .str.upper()
)

local["timestamp_utc"] = pd.to_datetime(
    local["timestamp_utc"],
    utc=True,
)

local["trade_date"] = pd.to_datetime(
    local["trade_date"]
).dt.date

local = local[
    local["symbol"] == SYMBOL
].copy()

print()
print("=" * 80)
print("LOCAL ALTERNATIVE-C2 CACHE")
print("=" * 80)

print(f"Rows:          {len(local):,}")
print(
    f"Trading days:  "
    f"{local['trade_date'].nunique():,}"
)
print(
    f"First date:    "
    f"{local['trade_date'].min()}"
)
print(
    f"Last date:     "
    f"{local['trade_date'].max()}"
)


# ============================================================
# CONNECT TO SUPABASE
# ============================================================

print()
print("Connecting to Supabase...")

conn = psycopg.connect(
    host=os.environ["SUPABASE_DB_HOST"],
    port=5432,
    dbname="postgres",
    user=os.environ["SUPABASE_DB_USER"],
    password=os.environ["SUPABASE_DB_PASSWORD"],
    sslmode="require",
)

print("Connected.")


# ============================================================
# LOAD EXISTING CANONICAL AAPL DATA
# ============================================================

query = """
    select
        symbol,
        trade_date,
        timestamp_utc,
        timestamp_ms,
        open,
        high,
        low,
        close,
        volume,
        vwap,
        transactions
    from public.market_intraday_history
    where symbol = %s
      and timeframe = '1m'
      and data_source = 'massive_1m'
      and adjusted = true
    order by timestamp_utc
"""

with conn.cursor() as cur:
    cur.execute(query, (SYMBOL,))
    rows = cur.fetchall()
    columns = [
        desc.name
        for desc in cur.description
    ]

conn.close()

db = pd.DataFrame(
    rows,
    columns=columns,
)

if db.empty:
    raise RuntimeError(
        "No existing adjusted=true AAPL rows "
        "found in market_intraday_history."
    )

db["timestamp_utc"] = pd.to_datetime(
    db["timestamp_utc"],
    utc=True,
)

db["trade_date"] = pd.to_datetime(
    db["trade_date"]
).dt.date

print()
print("=" * 80)
print("EXISTING SUPABASE AAPL CACHE")
print("=" * 80)

print(f"Rows:          {len(db):,}")
print(
    f"Trading days:  "
    f"{db['trade_date'].nunique():,}"
)
print(
    f"First date:    "
    f"{db['trade_date'].min()}"
)
print(
    f"Last date:     "
    f"{db['trade_date'].max()}"
)


# ============================================================
# RESTRICT LOCAL CACHE TO EXISTING DB DAYS
# ============================================================

db_days = set(
    db["trade_date"].unique()
)

local_overlap = local[
    local["trade_date"].isin(
        db_days
    )
].copy()

print()
print("=" * 80)
print("OVERLAP POPULATION")
print("=" * 80)

print(
    f"DB signal-days:      "
    f"{len(db_days):,}"
)

print(
    f"Local overlap days:  "
    f"{local_overlap['trade_date'].nunique():,}"
)

print(
    f"DB overlap rows:     "
    f"{len(db):,}"
)

print(
    f"Local overlap rows:  "
    f"{len(local_overlap):,}"
)


# ============================================================
# MERGE BY EXACT TIMESTAMP
# ============================================================

compare_cols = [
    "timestamp_utc",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vwap",
    "transactions",
]

merged = db[compare_cols].merge(
    local_overlap[compare_cols],
    on="timestamp_utc",
    how="outer",
    suffixes=("_db", "_local"),
    indicator=True,
)

only_db = int(
    (merged["_merge"] == "left_only").sum()
)

only_local = int(
    (merged["_merge"] == "right_only").sum()
)

matched = merged[
    merged["_merge"] == "both"
].copy()

print()
print("=" * 80)
print("TIMESTAMP COVERAGE")
print("=" * 80)

print(
    f"Matched timestamps:  "
    f"{len(matched):,}"
)

print(
    f"DB-only timestamps:  "
    f"{only_db:,}"
)

print(
    f"Local-only timestamps:"
    f" {only_local:,}"
)


# ============================================================
# NUMERIC COMPARISON HELPERS
# ============================================================

def numeric_series(series):
    return pd.to_numeric(
        series,
        errors="coerce",
    )


def difference_stats(
    field: str,
    tolerance: float,
):
    left = numeric_series(
        matched[f"{field}_db"]
    )

    right = numeric_series(
        matched[f"{field}_local"]
    )

    both_null = (
        left.isna()
        & right.isna()
    )

    one_null = (
        left.isna()
        ^ right.isna()
    )

    comparable = (
        ~left.isna()
        & ~right.isna()
    )

    diff = (
        left[comparable]
        - right[comparable]
    ).abs()

    mismatch_n = int(
        (diff > tolerance).sum()
        + one_null.sum()
    )

    max_diff = (
        float(diff.max())
        if len(diff)
        else 0.0
    )

    return {
        "field": field,
        "comparable_n":
            int(comparable.sum()),
        "both_null_n":
            int(both_null.sum()),
        "one_null_n":
            int(one_null.sum()),
        "mismatch_n":
            mismatch_n,
        "max_abs_diff":
            max_diff,
        "tolerance":
            tolerance,
    }


# ============================================================
# COMPARE CORE FIELDS
# ============================================================

results = []

for field in [
    "open",
    "high",
    "low",
    "close",
]:
    results.append(
        difference_stats(
            field,
            PRICE_TOLERANCE,
        )
    )

results.append(
    difference_stats(
        "volume",
        VOLUME_TOLERANCE,
    )
)

results.append(
    difference_stats(
        "vwap",
        VWAP_TOLERANCE,
    )
)

# Transactions should be exact when both present.
results.append(
    difference_stats(
        "transactions",
        0.0,
    )
)

result_df = pd.DataFrame(
    results
)


# ============================================================
# TRADE-DATE CHECK
# ============================================================

trade_date_mismatch_n = int(
    (
        matched["trade_date_db"]
        != matched["trade_date_local"]
    ).sum()
)


# ============================================================
# FINAL REPORT
# ============================================================

print()
print("=" * 80)
print("FIELD PARITY")
print("=" * 80)

print(
    result_df.to_string(
        index=False
    )
)

print()
print(
    f"Trade-date mismatches: "
    f"{trade_date_mismatch_n:,}"
)


core_fields = [
    "open",
    "high",
    "low",
    "close",
    "volume",
]

core_mismatches = int(
    result_df.loc[
        result_df["field"].isin(
            core_fields
        ),
        "mismatch_n",
    ].sum()
)

vwap_mismatches = int(
    result_df.loc[
        result_df["field"] == "vwap",
        "mismatch_n",
    ].sum()
)

transactions_mismatches = int(
    result_df.loc[
        result_df["field"] == "transactions",
        "mismatch_n",
    ].sum()
)


print()
print("=" * 80)
print("AAPL OVERLAP PARITY GATE")
print("=" * 80)

gate_pass = (
    only_db == 0
    and trade_date_mismatch_n == 0
    and core_mismatches == 0
)

print(
    f"Core OHLCV mismatches: "
    f"{core_mismatches:,}"
)

print(
    f"VWAP mismatches:       "
    f"{vwap_mismatches:,}"
)

print(
    f"Transactions mismatch: "
    f"{transactions_mismatches:,}"
)

print()

if gate_pass:
    print(
        "RESULT: PASS — newly acquired "
        "adjusted=true AAPL bars reproduce "
        "the existing canonical Massive OHLCV "
        "on overlapping timestamps."
    )
else:
    print(
        "RESULT: FAIL — do NOT launch the "
        "112-symbol acquisition yet."
    )

print()

if not gate_pass:
    raise SystemExit(1)