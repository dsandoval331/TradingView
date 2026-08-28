import requests
from getpass import getpass

API_KEY = getpass("Enter your Massive API key: ").strip()

# Candidate Massive/Polygon index tickers.
# We are testing availability first — not assuming these work.
INDEXES = {
    "Dow Jones Industrial Average": "I:DJI",
    "Nasdaq Composite": "I:COMP",
    "S&P 500": "I:SPX",
}

START_DATE = "2026-08-01"
END_DATE = "2026-08-27"

print()
print("MASSIVE INDEX AVAILABILITY TEST")
print("=" * 70)

for name, ticker in INDEXES.items():

    print()
    print(f"Testing {name}")
    print(f"Ticker candidate: {ticker}")

    url = (
        f"https://api.massive.com/v2/aggs/ticker/{ticker}"
        f"/range/1/day/{START_DATE}/{END_DATE}"
    )

    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": 5000,
        "apiKey": API_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=30)

        print(f"HTTP status: {response.status_code}")

        data = response.json()

        print(f"API status: {data.get('status')}")
        print(f"Results count: {data.get('resultsCount', 0)}")

        rows = data.get("results", [])

        if rows:
            print("SUCCESS — DATA RETURNED")

            first = rows[0]
            last = rows[-1]

            print(
                "First bar:",
                first.get("o"),
                first.get("h"),
                first.get("l"),
                first.get("c")
            )

            print(
                "Last bar:",
                last.get("o"),
                last.get("h"),
                last.get("l"),
                last.get("c")
            )

        else:
            print("NO INDEX DATA RETURNED")

            # Print useful API message if one exists
            if data.get("error"):
                print("Error:", data.get("error"))

            if data.get("message"):
                print("Message:", data.get("message"))

    except Exception as error:
        print("REQUEST FAILED")
        print(error)

print()
print("=" * 70)
print("INDEX TEST COMPLETE")