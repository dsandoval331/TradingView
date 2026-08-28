import os
import requests
import pandas as pd
from getpass import getpass

API_KEY = getpass("Enter your Massive API key: ").strip()

SERIES = {
    "DIA": "DIA",
    "NASDAQ_COMPOSITE": "I:COMP",
}

START_DATE = "2025-06-01"
END_DATE = "2026-08-27"

OUTPUT_FOLDER = os.path.join(
    os.path.expanduser("~"),
    "Downloads",
    "Massive_Market_Validation"
)

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def download_daily_bars(label, ticker):

    print()
    print("=" * 70)
    print(f"Downloading {label}")
    print(f"Ticker: {ticker}")
    print("=" * 70)

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

    print(f"HTTP status: {response.status_code}")

    response.raise_for_status()

    data = response.json()

    rows = data.get("results", [])

    if not rows:
        print(f"WARNING: No rows returned for {label}")
        print(data)
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
        f"{label}_massive_daily.csv"
    )

    df.to_csv(
        output_file,
        index=False
    )

    print(f"SUCCESS: {label}")
    print(f"Rows:       {len(df)}")
    print(f"First date: {df['trade_date'].min()}")
    print(f"Last date:  {df['trade_date'].max()}")
    print(f"Saved to:   {output_file}")

    return len(df)


print()
print("MASSIVE MARKET VALIDATION DOWNLOAD")
print(f"Period: {START_DATE} through {END_DATE}")
print()

results = {}

for label, ticker in SERIES.items():
    try:
        result = download_daily_bars(label, ticker)

        if result is not None:
            results[label] = result

    except Exception as error:
        print(f"ERROR downloading {label}:")
        print(error)


print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)

for label in SERIES:
    if label in results:
        print(f"{label}: {results[label]} rows - SUCCESS")
    else:
        print(f"{label}: FAILED")

print()
print("Files saved in:")
print(OUTPUT_FOLDER)