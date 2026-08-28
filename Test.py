# Test script

import requests
import pandas as pd
from zoneinfo import ZoneInfo

# ============================================================
# CONFIG
# ============================================================

API_KEY = input("Enter your Massive API key: ").strip()

if not API_KEY:
    raise ValueError("Massive API key cannot be blank.")

SYMBOL = "AAPL"
DATE = "2026-08-27"

# ============================================================
# MASSIVE 1-MINUTE AGGREGATES
# ============================================================

url = (
    f"https://api.massive.com/v2/aggs/ticker/{SYMBOL}"
    f"/range/1/minute/{DATE}/{DATE}"
)

params = {
    "adjusted": "true",
    "sort": "asc",
    "limit": 50000,
    "apiKey": API_KEY,
}

print(f"Downloading {SYMBOL} 1-minute bars for {DATE}...")

response = requests.get(url, params=params, timeout=60)

print("HTTP status:", response.status_code)

response.raise_for_status()

data = response.json()

print("API status:", data.get("status"))
print("Results count:", data.get("resultsCount"))

results = data.get("results", [])

if not results:
    raise RuntimeError("No minute bars were returned.")

# ============================================================
# CONVERT TO DATAFRAME
# ============================================================

df = pd.DataFrame(results)

df = df.rename(
    columns={
        "t": "timestamp_ms",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "vw": "vwap",
        "n": "transactions",
    }
)

# Massive timestamps are Unix milliseconds.
df["timestamp_utc"] = pd.to_datetime(
    df["timestamp_ms"],
    unit="ms",
    utc=True
)

df["timestamp_et"] = (
    df["timestamp_utc"]
    .dt.tz_convert("America/New_York")
)

# ============================================================
# FILTER TO 04:00–10:00 ET
# ============================================================

df["et_time"] = df["timestamp_et"].dt.time

start_time = pd.Timestamp("04:00").time()
end_time = pd.Timestamp("10:00").time()

research = df[
    (df["et_time"] >= start_time) &
    (df["et_time"] <= end_time)
].copy()

# ============================================================
# OUTPUT
# ============================================================

print()
print("FULL-DAY BARS:", len(df))
print("04:00–10:00 ET BARS:", len(research))

print()
print("FIRST 10 RESEARCH BARS:")
print(
    research[
        [
            "timestamp_et",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "vwap",
            "transactions",
        ]
    ].head(10).to_string(index=False)
)

print()
print("LAST 10 RESEARCH BARS:")
print(
    research[
        [
            "timestamp_et",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "vwap",
            "transactions",
        ]
    ].tail(10).to_string(index=False)
)

# ============================================================
# SAVE TEST FILE
# ============================================================

filename = f"{SYMBOL}_1m_{DATE}_0400_1000_ET.csv"

research.to_csv(filename, index=False)

print()
print("Saved:", filename)