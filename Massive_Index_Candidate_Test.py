import requests
from getpass import getpass

API_KEY = getpass("Enter your Massive API key: ").strip()

start_date = "2025-06-01"
end_date = "2026-08-27"

candidates = [
    # S&P 500 candidates
    ("S&P 500", "I:SPX"),
    ("S&P 500", "SPX"),
    ("S&P 500 ETF proxy", "SPY"),

    # Dow candidates
    ("Dow Jones Industrial Average", "I:DJI"),
    ("Dow Jones Industrial Average", "DJI"),
    ("Dow ETF proxy", "DIA"),
]

print()
print("MASSIVE MARKET INDEX CANDIDATE TEST")
print("=" * 70)

for description, ticker in candidates:

    url = (
        f"https://api.massive.com/v2/aggs/ticker/{ticker}"
        f"/range/1/day/{start_date}/{end_date}"
    )

    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": 50000,
        "apiKey": API_KEY,
    }

    print()
    print(f"Testing: {description}")
    print(f"Ticker:  {ticker}")

    try:
        response = requests.get(url, params=params, timeout=30)

        print(f"HTTP status: {response.status_code}")

        try:
            data = response.json()
        except Exception:
            print("ERROR: Response was not valid JSON.")
            print(response.text[:500])
            continue

        print(f"API status: {data.get('status')}")
        print(f"Results count: {data.get('resultsCount', 0)}")

        rows = data.get("results", [])

        if response.status_code == 200 and rows:

            first = rows[0]
            last = rows[-1]

            print("SUCCESS — DATA RETURNED")
            print(
                "First bar:",
                first.get("o"),
                first.get("h"),
                first.get("l"),
                first.get("c"),
            )
            print(
                "Last bar:",
                last.get("o"),
                last.get("h"),
                last.get("l"),
                last.get("c"),
            )

        else:

            print("NO DATA RETURNED")

            message = (
                data.get("message")
                or data.get("error")
                or data.get("status")
            )

            if message:
                print(f"Message: {message}")

    except requests.RequestException as e:
        print(f"REQUEST ERROR: {e}")

print()
print("=" * 70)
print("TEST COMPLETE")