import os
import requests
import pandas as pd
from getpass import getpass

# ============================================================
# CONFIGURATION
# ============================================================

API_KEY = getpass("Enter your Massive API key: ").strip()

# First validate normal equities / ETF.
# We'll handle direct indexes separately after these pass.
TICKERS = [
    "CVX",
    "DELL",
    "MSFT",
    "SPY",
]

START_DATE = "2025-06-01"
END_DATE = "2026-08-27"

OUTPUT_FOLDER = os.path.join(
    os.path.expanduser("~"),
    "Downloads",
    "Massive_Validation"
)

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ============================================================
# DOWNLOAD FUNCTION
# ============================================================

def download_daily_bars(ticker):

    print()
    print("=" * 65)
    print(f"Downloading {ticker}...")
    print("=" * 65)

    url = (
        f"https://api.massive.com/v2/aggs/ticker/{ticker}"
        f"/range/1/day/{START_DATE}/{END_DATE}"
    )

    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": 50000,
        "apiKey": API_KEY
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    rows = data.get("results", [])

    if not rows:
        print(f"WARNING: No daily bars returned for {ticker}.")
        print(f"Response status: {data.get('status')}")
        return None

    df = pd.DataFrame(rows)

    df = df.rename(columns={
        "t": "timestamp_ms",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "vw": "vwap",
        "n": "transactions"
    })

    df["trade_date"] = pd.to_datetime(
        df["timestamp_ms"],
        unit="ms",
        utc=True
    ).dt.tz_convert("America/New_York").dt.date

    wanted = [
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
        "transactions",
        "timestamp_ms"
    ]

    df = df[
        [column for column in wanted if column in df.columns]
    ]

    output_file = os.path.join(
        OUTPUT_FOLDER,
        f"{ticker}_massive_daily.csv"
    )

    df.to_csv(
        output_file,
        index=False
    )

    print(f"SUCCESS: {ticker}")
    print(f"Daily bars: {len(df)}")
    print(f"First date: {df['trade_date'].min()}")
    print(f"Last date:  {df['trade_date'].max()}")
    print(f"Saved to:   {output_file}")

    return df


# ============================================================
# RUN VALIDATION DOWNLOADS
# ============================================================

print()
print("MASSIVE DAILY DATA VALIDATION")
print(f"Tickers: {', '.join(TICKERS)}")
print(f"Period:  {START_DATE} through {END_DATE}")
print(f"Output:  {OUTPUT_FOLDER}")

results = {}

for ticker in TICKERS:

    try:

        df = download_daily_bars(ticker)

        if df is not None:
            results[ticker] = len(df)

    except Exception as error:

        print()
        print(f"ERROR downloading {ticker}:")
        print(error)


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 65)
print("DOWNLOAD SUMMARY")
print("=" * 65)

for ticker in TICKERS:

    if ticker in results:
        print(f"{ticker}: {results[ticker]} daily bars - SUCCESS")
    else:
        print(f"{ticker}: FAILED / NO DATA")

print()
print(f"Files saved in:")
print(OUTPUT_FOLDER)
print()
print("Validation download complete.")