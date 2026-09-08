from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests


ROOT = Path.cwd()

LEDGER = (
    ROOT
    / "data"
    / "second1m_alt_entry_prospective_v1"
    / "events"
    / "altc2_prospective_event_ledger_v1.parquet"
)

RUNNER = ROOT / "run_altc2_prospective_validation_v1_6.py"
REPORTER = ROOT / "report_altc2_prospective_checkpoint_v1.py"


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
        result["state"] = (
            "AVAILABLE_WITH_DATA"
            if result["results_count"] > 0
            else "ACCESSIBLE_NO_DATA"
        )
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
    elif response.status_code == 401:
        result["state"] = "AUTH_FAILED"
    elif response.status_code == 429:
        result["state"] = "RATE_LIMITED"
    else:
        result["state"] = f"HTTP_{response.status_code}"

    return result


def find_latest_available_date(
    api_key: str,
    start_date: date,
    lookback_days: int,
    symbol: str,
) -> date | None:
    print("=" * 88)
    print("A36.5A - MASSIVE AVAILABILITY DISCOVERY")
    print("=" * 88)
    print(f"Probe symbol:       {symbol}")
    print(f"Newest probe date:  {start_date.isoformat()}")
    print(f"Calendar lookback:  {lookback_days} days")
    print()
    print(f"{'DATE':<12} {'HTTP':>5} {'STATE':<22} {'RESULTS':>8}")
    print("-" * 88)

    for offset in range(lookback_days):
        target = start_date - timedelta(days=offset)

        while True:
            result = probe_day(
                api_key=api_key,
                target_date=target,
                symbol=symbol,
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

            if result["state"] == "RATE_LIMITED":
                print("Rate limited; waiting 20 seconds before one retry...")
                time.sleep(20)
                retry = probe_day(
                    api_key=api_key,
                    target_date=target,
                    symbol=symbol,
                )
                if retry["state"] == "RATE_LIMITED":
                    raise RuntimeError(
                        "Massive rate limit persisted after retry. "
                        "Wait and run the updater again."
                    )
                result = retry

                results_text = (
                    "-"
                    if result["results_count"] is None
                    else f"{result['results_count']:,}"
                )
                print(
                    f"{target.isoformat():<12} "
                    f"{result['http_status']:>5} "
                    f"{result['state']:<22} "
                    f"{results_text:>8}  (retry)"
                )

            break

        if result["state"] == "AVAILABLE_WITH_DATA":
            return target

    return None


def ledger_max_trade_date() -> date | None:
    if not LEDGER.exists():
        return None

    df = pd.read_parquet(
        LEDGER,
        columns=["trade_date"],
    )

    if df.empty:
        return None

    dates = pd.to_datetime(
        df["trade_date"],
        errors="coerce",
    ).dropna()

    if dates.empty:
        return None

    return dates.max().date()


def run_and_tee(
    command: list[str],
    log_path: Path,
    env: dict[str, str],
) -> int:
    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("COMMAND:")
    print(" ".join(command))
    print(f"Log: {log_path}")
    print()

    with log_path.open(
        "w",
        encoding="utf-8",
    ) as log:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert process.stdout is not None

        for line in process.stdout:
            print(
                line,
                end="",
            )
            log.write(
                line
            )
            log.flush()

        return process.wait()


def run_reporter() -> int:
    if not REPORTER.exists():
        print(
            f"WARNING: checkpoint reporter not found: {REPORTER}"
        )
        return 0

    print()
    print("=" * 88)
    print("CHECKPOINT REPORT")
    print("=" * 88)

    return subprocess.call(
        [
            sys.executable,
            str(REPORTER),
        ],
        cwd=ROOT,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "One-command Alternative C2 prospective updater. "
            "Finds the newest Massive-accessible trading date, compares it "
            "with the frozen prospective ledger, and only runs V1.6 when "
            "new accessible data exists."
        )
    )
    parser.add_argument(
        "--start-date",
        help=(
            "Newest calendar date to probe in YYYY-MM-DD format. "
            "Defaults to today's local date."
        ),
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--symbol",
        default="AAPL",
    )
    parser.add_argument(
        "--report-only-if-current",
        action="store_true",
        help=(
            "If no new accessible date exists, still run the checkpoint "
            "reporter before exiting."
        ),
    )
    args = parser.parse_args()

    if not RUNNER.exists():
        raise FileNotFoundError(
            f"Prospective runner not found: {RUNNER}"
        )

    start_date = (
        parse_date(args.start_date)
        if args.start_date
        else date.today()
    )

    api_key = resolve_api_key()

    latest = find_latest_available_date(
        api_key=api_key,
        start_date=start_date,
        lookback_days=args.lookback_days,
        symbol=args.symbol.upper(),
    )

    print()
    print("=" * 88)
    print("A36.5A - PROSPECTIVE UPDATE DECISION")
    print("=" * 88)

    if latest is None:
        print(
            "LATEST AVAILABLE TRADING DATE: NONE FOUND "
            "WITHIN LOOKBACK"
        )
        print("RESULT: NO UPDATE RUN")
        return

    ledger_max = ledger_max_trade_date()

    print(
        "Latest Massive-accessible trading date: "
        f"{latest.isoformat()}"
    )
    print(
        "Latest trade date already in ledger:     "
        f"{ledger_max.isoformat() if ledger_max else 'NONE'}"
    )

    if (
        ledger_max is not None
        and latest <= ledger_max
    ):
        print()
        print(
            "No newer accessible trading date exists. "
            "The prospective ledger is already current "
            "through the latest available Massive date."
        )
        print("RESULT: LEDGER CURRENT")

        if args.report_only_if_current:
            rc = run_reporter()
            if rc != 0:
                raise SystemExit(rc)

        return

    print()
    print(
        "New accessible prospective data detected. "
        f"Explicit run end date: {latest.isoformat()}"
    )
    print(
        "No silent fallback is being used; this exact date was "
        "selected from the availability probe above."
    )

    env = os.environ.copy()
    env["MASSIVE_API_KEY"] = api_key

    log_path = (
        ROOT
        / f"altc2_prospective_run_{latest.isoformat()}_v1_6.txt"
    )

    rc = run_and_tee(
        [
            sys.executable,
            str(RUNNER),
            "--end-date",
            latest.isoformat(),
        ],
        log_path=log_path,
        env=env,
    )

    if rc != 0:
        print()
        print(
            f"RESULT: PROSPECTIVE RUN FAILED (exit code {rc})"
        )
        raise SystemExit(rc)

    rc = run_reporter()

    if rc != 0:
        print()
        print(
            f"RESULT: CHECKPOINT REPORT FAILED (exit code {rc})"
        )
        raise SystemExit(rc)

    print()
    print("=" * 88)
    print("A36.5A UPDATE COMPLETE")
    print("=" * 88)
    print(
        f"Prospective ledger updated through accessible date: "
        f"{latest.isoformat()}"
    )
    print(f"Run log: {log_path}")
    print("RESULT: COMPLETE")


if __name__ == "__main__":
    main()
