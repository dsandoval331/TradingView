from __future__ import annotations

import argparse
import json
import os
from getpass import getpass
from typing import Any, Dict

import requests

BASE_URL = "https://api.massive.com"


def get_key() -> str:
    key = os.getenv("MASSIVE_API_KEY", "").strip()
    if not key:
        key = getpass("Massive API key (not stored): ").strip()
    if not key:
        raise SystemExit("Massive API key is required")
    return key


def probe(session: requests.Session, name: str, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = BASE_URL + path
    try:
        resp = session.get(url, params=params, timeout=30)
        out: Dict[str, Any] = {"name": name, "status_code": resp.status_code}
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        out["status"] = payload.get("status")
        out["error"] = payload.get("error") or payload.get("message")
        results = payload.get("results")
        out["result_count"] = len(results) if isinstance(results, list) else (1 if results else 0)
        if isinstance(results, list) and results:
            sample = results[0]
            out["sample_keys"] = sorted(sample.keys()) if isinstance(sample, dict) else []
        elif isinstance(results, dict):
            out["sample_keys"] = sorted(results.keys())
        return out
    except requests.RequestException as exc:
        return {"name": name, "status_code": None, "error": str(exc)}


def main() -> None:
    p = argparse.ArgumentParser(description="Read-only Massive entitlement probe for SWING_10D_EDGE S1.")
    p.add_argument("--symbol", default="AAPL")
    args = p.parse_args()

    api_key = get_key()
    session = requests.Session()
    common = {"apiKey": api_key, "limit": 5}

    probes = [
        ("daily_2021", f"/v2/aggs/ticker/{args.symbol}/range/1/day/2021-01-04/2021-01-08", {**common, "adjusted": "false", "sort": "asc"}),
        ("daily_2016", f"/v2/aggs/ticker/{args.symbol}/range/1/day/2016-01-04/2016-01-08", {**common, "adjusted": "false", "sort": "asc"}),
        ("daily_2004", f"/v2/aggs/ticker/{args.symbol}/range/1/day/2004-01-05/2004-01-09", {**common, "adjusted": "false", "sort": "asc"}),
        ("ticker_asof_2021", "/v3/reference/tickers", {**common, "ticker": args.symbol, "date": "2021-01-04", "active": "true"}),
        ("delisted_tickers", "/v3/reference/tickers", {**common, "active": "false", "market": "stocks", "sort": "ticker"}),
        ("splits", "/stocks/v1/splits", {**common, "ticker": args.symbol}),
        ("dividends", "/stocks/v1/dividends", {**common, "ticker": args.symbol}),
    ]

    results = [probe(session, name, path, params) for name, path, params in probes]
    print(json.dumps({"symbol": args.symbol.upper(), "read_only": True, "probes": results}, indent=2))


if __name__ == "__main__":
    main()
