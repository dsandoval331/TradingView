from __future__ import annotations

import argparse
import getpass
import os
from datetime import date, datetime, timedelta
from typing import Any

import requests


def looks_like_shell_command(value: str | None) -> bool:
    if not value:
        return False

    lowered = value.lower()
    suspicious_tokens = [
        "$env:",
        "get-clipboard",
        "massive_api_key =",
        "set-item env:",
    ]
    return any(token in lowered for token in suspicious_tokens)


def resolve_api_key() -> str:
    key = os.environ.get("MASSIVE_API_KEY")

    if looks_like_shell_command(key):
        print(
            "WARNING: MASSIVE_API_KEY looks like a shell command, "
            "not a raw API key."
        )
        key = None

    if not key:
        key = getpass.getpass("Enter Massive API key: ").strip()

    if not key:
        raise RuntimeError("Massive API key was not provided.")

    if looks_like_shell_command(key):
        raise RuntimeError(
            "Supplied value still looks like a shell command. "
            "Paste only the raw API key."
        )

    return key


def parse_date(text: str) -> date:
    return datetime.strptime(text, "%Y-%m-%d").date()


def probe_day(
    api_key: str,
    target_date: date,
    symbol: str = "AAPL",
) -> dict[str, Any]:
    d = target_date.isoformat()
    url = (
        f"https://api.massive.com/v2/aggs/ticker/{symbol}"
        f"/range/1/minute/{d}/{d}"
    )

    response = requests.get(
        url,
        params={
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": api_key,
        },
        timeout=60,
    )

    result: dict[str, Any] = {
        "date": target_date,
        "http_status": response.status_code,
        "state": "UNKNOWN",
        "results_count": None,
        "message": "",
    }

    payload: dict[str, Any] = {}
    try:
        payload = response.json()
    except Exception:
        pass

    if response.status_code == 200:
        results_count = payload.get("resultsCount")
        if results_count is None:
            results = payload.get("results")
            results_count = len(results) if isinstance(results, list) else 0

        result["results_count"] = int(results_count or 0)

        if result["results_count"] > 0:
            result["state"] = "AVAILABLE_WITH_DATA"
        else:
            result["state"] = "ACCESSIBLE_NO_DATA"

        return result

    message = str(
        payload.get("message")
        or payload.get("error")
        or payload.get("status")
        or response.text[:500]
        or ""
    ).strip()
    result["message"] = message

    if response.status_code == 403:
        result["state"] = "NOT_ENTITLED"
        return result

    if response.status_code == 401:
        result["state"] = "AUTH_FAILED"
        return result

    result["state"] = f"HTTP_{response.status_code}"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only helper that finds the newest AAPL trading date "
            "currently accessible under the user's Massive plan. "
            "It never modifies the Alternative C2 cache or ledger."
        )
    )
    parser.add_argument(
        "--start-date",
        help=(
            "Newest date to probe in YYYY-MM-DD format. "
            "Defaults to today's local calendar date."
        ),
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=10,
        help="Maximum calendar days to inspect backward. Default: 10.",
    )
    parser.add_argument(
        "--symbol",
        default="AAPL",
        help="Probe symbol. Default: AAPL.",
    )
    args = parser.parse_args()

    if args.lookback_days < 1:
        raise ValueError("--lookback-days must be >= 1")

    start_date = (
        parse_date(args.start_date)
        if args.start_date
        else date.today()
    )

    api_key = resolve_api_key()

    print("=" * 88)
    print("ALT C2 - MASSIVE LATEST AVAILABLE DATE CHECK V1")
    print("=" * 88)
    print(f"Probe symbol:       {args.symbol.upper()}")
    print(f"Newest probe date:  {start_date.isoformat()}")
    print(f"Calendar lookback:  {args.lookback_days} days")
    print()
    print(
        f"{'DATE':<12} {'HTTP':>5} {'STATE':<22} {'RESULTS':>8}"
    )
    print("-" * 88)

    newest_available: date | None = None

    for offset in range(args.lookback_days):
        target = start_date - timedelta(days=offset)
        result = probe_day(
            api_key=api_key,
            target_date=target,
            symbol=args.symbol.upper(),
        )

        results_text = (
            "-"
            if result["results_count"] is None
            else f"{result['results_count']:,}"
        )

        print(
            f"{target.isoformat():<12} "
            f"{result['http_status']:>5} "
            f"{result['state']:<22} "
            f"{results_text:>8}"
        )

        if result["state"] == "AUTH_FAILED":
            raise RuntimeError(
                "Massive authentication failed. Verify the API key."
            )

        if (
            newest_available is None
            and result["state"] == "AVAILABLE_WITH_DATA"
        ):
            newest_available = target

    print()
    if newest_available is None:
        print(
            "LATEST AVAILABLE TRADING DATE: NONE FOUND "
            "WITHIN REQUESTED LOOKBACK"
        )
        print("RESULT: NO ELIGIBLE DATE FOUND")
        return

    print(
        "LATEST AVAILABLE TRADING DATE: "
        f"{newest_available.isoformat()}"
    )
    print()
    print("Suggested explicit prospective command:")
    print(
        "python .\\run_altc2_prospective_validation_v1_6.py "
        f"--end-date {newest_available.isoformat()}"
    )
    print()
    print(
        "This helper is read-only. It does not automatically run the "
        "prospective pipeline or silently change the requested validation date."
    )
    print("RESULT: DATE CHECK COMPLETE")


if __name__ == "__main__":
    main()
