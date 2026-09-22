"""Read-only Alpha Vantage entitlement/delisted-security probe for SWING_10D_EDGE S1.

Prompts once for ALPHAVANTAGE_API_KEY if the environment variable is absent.
Never stores or prints the key. Makes GET requests only.
"""
from __future__ import annotations
import csv, getpass, io, json, os
from urllib.parse import urlencode
import requests

BASE_URL = "https://www.alphavantage.co/query"

def _get(key: str, **params):
    params["apikey"] = key
    try:
        r = requests.get(BASE_URL, params=params, timeout=30)
        text = r.text
        out = {"status_code": r.status_code, "content_type": r.headers.get("content-type", "")}
        try:
            payload = r.json()
            out["api_message"] = payload.get("Information") or payload.get("Note") or payload.get("Error Message")
            ts = payload.get("Time Series (Daily)")
            if isinstance(ts, dict):
                dates = sorted(ts)
                out.update({"result_count": len(dates), "min_date": dates[0] if dates else None,
                            "max_date": dates[-1] if dates else None,
                            "sample_keys": list(next(iter(ts.values())).keys()) if ts else []})
            elif isinstance(payload, dict):
                out["top_level_keys"] = list(payload.keys())[:12]
        except ValueError:
            rows = list(csv.DictReader(io.StringIO(text)))
            out["result_count"] = len(rows)
            if rows:
                out["sample_keys"] = list(rows[0].keys())
                out["sample"] = {k: rows[0].get(k) for k in list(rows[0].keys())[:8]}
        return out
    except Exception as exc:
        return {"status_code": None, "error": type(exc).__name__ + ": " + str(exc)}

def main():
    key = os.getenv("ALPHAVANTAGE_API_KEY") or getpass.getpass("Alpha Vantage API key (not stored): ")
    probes = []
    tests = [
        ("daily_full_aapl", dict(function="TIME_SERIES_DAILY", symbol="AAPL", outputsize="full")),
        ("listing_active_2013", dict(function="LISTING_STATUS", date="2013-08-05", state="active", datatype="csv")),
        ("listing_delisted_2013", dict(function="LISTING_STATUS", date="2013-08-05", state="delisted", datatype="csv")),
        # TWTR is a known delisted US equity (delisted 2022); tests whether historical bars remain queryable.
        ("daily_full_twtr_delisted", dict(function="TIME_SERIES_DAILY", symbol="TWTR", outputsize="full")),
        ("earnings_history_aapl", dict(function="EARNINGS", symbol="AAPL")),
        ("earnings_calendar_aapl", dict(function="EARNINGS_CALENDAR", symbol="AAPL", horizon="12month", datatype="csv")),
    ]
    for name, params in tests:
        item = {"name": name}
        item.update(_get(key, **params))
        probes.append(item)
    print(json.dumps({"read_only": True, "provider": "Alpha Vantage", "probes": probes}, indent=2))

if __name__ == "__main__":
    main()
