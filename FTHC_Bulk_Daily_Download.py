import os
import time
from datetime import datetime
from getpass import getpass

import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

API_KEY = getpass("Enter your Massive API key: ").strip()

SYMBOL_FILE = os.path.join(
    os.path.expanduser("~"),
    "Downloads",
    "fthc_symbols.csv"
)

# Gives us substantial warm-up history before the earliest signals.
START_DATE = "2025-02-01"
END_DATE = "2026-08-27"

BASE_OUTPUT_FOLDER = os.path.join(
    os.path.expanduser("~"),
    "Downloads",
    "FTHC_Daily_History"
)

INDIVIDUAL_FOLDER = os.path.join(
    BASE_OUTPUT_FOLDER,
    "individual_symbols"
)

CONSOLIDATED_FILE = os.path.join(
    BASE_OUTPUT_FOLDER,
    "FTHC_daily_history_all_symbols.csv"
)

AUDIT_FILE = os.path.join(
    BASE_OUTPUT_FOLDER,
    "FTHC_daily_history_download_audit.csv"
)

os.makedirs(BASE_OUTPUT_FOLDER, exist_ok=True)
os.makedirs(INDIVIDUAL_FOLDER, exist_ok=True)

# Massive free stock plan is rate-limited.
# 13 seconds keeps us safely around 5 requests/minute.
REQUEST_DELAY_SECONDS = 13

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 20


# ============================================================
# LOAD SYMBOL UNIVERSE
# ============================================================

if not os.path.exists(SYMBOL_FILE):
    raise FileNotFoundError(
        f"Symbol file not found:\n{SYMBOL_FILE}"
    )

symbols_df = pd.read_csv(SYMBOL_FILE)

if "symbol" not in symbols_df.columns:
    raise RuntimeError(
        "fthc_symbols.csv must contain a column named 'symbol'."
    )

symbols = (
    symbols_df["symbol"]
    .dropna()
    .astype(str)
    .str.strip()
    .str.upper()
)

symbols = sorted(set(symbols))

if len(symbols) == 0:
    raise RuntimeError("No symbols were loaded.")

print()
print("=" * 75)
print("FTHC BULK DAILY-HISTORY DOWNLOAD")
print("=" * 75)
print(f"Symbols loaded: {len(symbols)}")
print(f"Start date:     {START_DATE}")
print(f"End date:       {END_DATE}")
print(f"Output folder:  {BASE_OUTPUT_FOLDER}")
print()


# ============================================================
# API SESSION
# ============================================================

session = requests.Session()


# ============================================================
# DOWNLOAD FUNCTION
# ============================================================

def download_symbol(ticker):
    url = (
        f"https://api.massive.com/v2/aggs/ticker/{ticker}"
        f"/range/1/day/{START_DATE}/{END_DATE}"
    )

    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": 50000,
        "apiKey": API_KEY,
    }

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(
                url,
                params=params,
                timeout=45
            )

            if response.status_code == 429:
                print(
                    f"  Rate limit hit for {ticker}. "
                    f"Waiting {RETRY_DELAY_SECONDS}s..."
                )
                time.sleep(RETRY_DELAY_SECONDS)
                continue

            response.raise_for_status()

            data = response.json()
            rows = data.get("results", [])

            if not rows:
                return None, "NO_DATA"

            df = pd.DataFrame(rows)

            df = df.rename(columns={
                "t": "timestamp_ms",
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume",
                "vw": "vwap",
                "n": "transactions",
            })

            df["trade_date"] = pd.to_datetime(
                df["timestamp_ms"],
                unit="ms",
                utc=True
            ).dt.tz_convert(
                "America/New_York"
            ).dt.date

            df.insert(0, "symbol", ticker)

            df["data_source"] = "massive"
            df["adjusted"] = True

            wanted = [
                "symbol",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "vwap",
                "transactions",
                "timestamp_ms",
                "data_source",
                "adjusted",
            ]

            df = df[
                [col for col in wanted if col in df.columns]
            ]

            df = (
                df
                .sort_values("trade_date")
                .drop_duplicates(
                    subset=["symbol", "trade_date"],
                    keep="last"
                )
                .reset_index(drop=True)
            )

            return df, "SUCCESS"

        except Exception as error:
            last_error = str(error)

            print(
                f"  Attempt {attempt}/{MAX_RETRIES} failed "
                f"for {ticker}: {error}"
            )

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    return None, f"ERROR: {last_error}"


# ============================================================
# MAIN DOWNLOAD LOOP
# ============================================================

all_frames = []
audit_rows = []

start_time = datetime.now()

for index, ticker in enumerate(symbols, start=1):
    print()
    print(f"[{index}/{len(symbols)}] Downloading {ticker}")

    symbol_start = datetime.now()

    df, status = download_symbol(ticker)

    elapsed_seconds = (
        datetime.now() - symbol_start
    ).total_seconds()

    if df is not None:
        output_file = os.path.join(
            INDIVIDUAL_FOLDER,
            f"{ticker}_daily.csv"
        )

        df.to_csv(
            output_file,
            index=False
        )

        duplicate_count = int(
            df.duplicated(
                subset=["symbol", "trade_date"]
            ).sum()
        )

        missing_ohlc = int(
            df[
                ["open", "high", "low", "close"]
            ].isna().any(axis=1).sum()
        )

        audit_rows.append({
            "symbol": ticker,
            "status": status,
            "rows": len(df),
            "first_date": df["trade_date"].min(),
            "last_date": df["trade_date"].max(),
            "duplicate_dates": duplicate_count,
            "missing_ohlc_rows": missing_ohlc,
            "elapsed_seconds": round(elapsed_seconds, 1),
        })

        all_frames.append(df)

        print(
            f"  SUCCESS — {len(df)} bars | "
            f"{df['trade_date'].min()} to "
            f"{df['trade_date'].max()}"
        )

    else:
        audit_rows.append({
            "symbol": ticker,
            "status": status,
            "rows": 0,
            "first_date": None,
            "last_date": None,
            "duplicate_dates": None,
            "missing_ohlc_rows": None,
            "elapsed_seconds": round(elapsed_seconds, 1),
        })

        print(f"  FAILED — {status}")

    if index < len(symbols):
        time.sleep(REQUEST_DELAY_SECONDS)


# ============================================================
# CONSOLIDATED OUTPUT
# ============================================================

if all_frames:
    combined = pd.concat(
        all_frames,
        ignore_index=True
    )

    combined = (
        combined
        .sort_values(
            ["symbol", "trade_date"]
        )
        .reset_index(drop=True)
    )

    combined.to_csv(
        CONSOLIDATED_FILE,
        index=False
    )

else:
    combined = pd.DataFrame()


# ============================================================
# AUDIT OUTPUT
# ============================================================

audit_df = pd.DataFrame(audit_rows)

audit_df.to_csv(
    AUDIT_FILE,
    index=False
)


# ============================================================
# FINAL VALIDATION SUMMARY
# ============================================================

successful_symbols = int(
    (audit_df["status"] == "SUCCESS").sum()
)

failed_symbols = (
    len(symbols) - successful_symbols
)

total_rows = len(combined)

duplicate_pairs = 0

if not combined.empty:
    duplicate_pairs = int(
        combined.duplicated(
            subset=["symbol", "trade_date"]
        ).sum()
    )

missing_ohlc_total = 0

if not combined.empty:
    missing_ohlc_total = int(
        combined[
            ["open", "high", "low", "close"]
        ].isna().any(axis=1).sum()
    )

runtime = datetime.now() - start_time


print()
print()
print("=" * 75)
print("DOWNLOAD COMPLETE")
print("=" * 75)

print(f"Requested symbols:      {len(symbols)}")
print(f"Successful symbols:     {successful_symbols}")
print(f"Failed symbols:         {failed_symbols}")
print(f"Total daily bars:       {total_rows}")
print(f"Duplicate symbol/dates: {duplicate_pairs}")
print(f"Missing OHLC rows:      {missing_ohlc_total}")

if not combined.empty:
    print(
        f"Overall first date:     "
        f"{combined['trade_date'].min()}"
    )

    print(
        f"Overall last date:      "
        f"{combined['trade_date'].max()}"
    )

print(
    f"Runtime:                "
    f"{runtime}"
)

print()
print("Consolidated CSV:")
print(CONSOLIDATED_FILE)

print()
print("Audit CSV:")
print(AUDIT_FILE)

print()
print("Individual symbol files:")
print(INDIVIDUAL_FOLDER)

print()
print("=" * 75)


# ============================================================
# DISPLAY FAILURES
# ============================================================

failures = audit_df[
    audit_df["status"] != "SUCCESS"
]

if not failures.empty:
    print()
    print("SYMBOLS REQUIRING ATTENTION")
    print(
        failures[
            ["symbol", "status"]
        ].to_string(index=False)
    )

else:
    print()
    print("ALL SYMBOLS DOWNLOADED SUCCESSFULLY.")