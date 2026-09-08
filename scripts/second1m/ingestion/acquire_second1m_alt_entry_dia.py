from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests


# =============================================================================
# CONFIG
# =============================================================================

ROOT = Path(r"C:\Users\DirtySouth\TradingResearch")

CACHE_ROOT = (
    ROOT
    / "data"
    / "second1m_alt_entry_cache_v1"
)

MANIFEST_ROOT = (
    CACHE_ROOT
    / "manifests"
)

MANIFEST_PATH = (
    MANIFEST_ROOT
    / "alt_entry_manifest.json"
)

SYMBOL = "DIA"

START_DATE = date(2025, 5, 23)
END_DATE = date(2026, 8, 27)

API_BASE = "https://api.massive.com"

ADJUSTED = "true"
MULTIPLIER = 1
TIMESPAN = "minute"

REQUEST_LIMIT = 50000

TIMEOUT_SECONDS = 60

SLEEP_BETWEEN_REQUESTS = 0.25

CACHE_VERSION = "SECOND1M_ALT_ENTRY_CACHE_V1"

DATA_SOURCE = "massive_1m"


# =============================================================================
# DATACLASSES
# =============================================================================

@dataclass
class PartitionSpec:
    symbol: str
    year: int
    start_date: date
    end_date: date
    output_path: Path


# =============================================================================
# HELPERS
# =============================================================================

def load_api_key() -> str:

    key = os.getenv(
        "MASSIVE_API_KEY",
        "",
    ).strip()

    if not key:
        raise RuntimeError(
            "MASSIVE_API_KEY is not set."
        )

    return key


def partition_path(
    symbol: str,
    year: int,
) -> Path:

    return (
        CACHE_ROOT
        / symbol
        / f"{symbol}_{year}.parquet"
    )


def build_partitions() -> list[PartitionSpec]:

    specs = []

    for year in range(
        START_DATE.year,
        END_DATE.year + 1,
    ):

        start = max(
            START_DATE,
            date(
                year,
                1,
                1,
            ),
        )

        end = min(
            END_DATE,
            date(
                year,
                12,
                31,
            ),
        )

        specs.append(
            PartitionSpec(
                symbol=SYMBOL,
                year=year,
                start_date=start,
                end_date=end,
                output_path=partition_path(
                    SYMBOL,
                    year,
                ),
            )
        )

    return specs


def request_json(
    url: str,
    params: dict[str, Any],
) -> dict[str, Any]:

    response = requests.get(
        url,
        params=params,
        timeout=TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    return response.json()


def download_partition(
    spec: PartitionSpec,
    api_key: str,
) -> pd.DataFrame:

    url = (
        f"{API_BASE}"
        f"/v2/aggs/ticker/"
        f"{spec.symbol}"
        f"/range/"
        f"{MULTIPLIER}"
        f"/{TIMESPAN}/"
        f"{spec.start_date.isoformat()}"
        f"/{spec.end_date.isoformat()}"
    )

    params = {
        "adjusted": ADJUSTED,
        "sort": "asc",
        "limit": REQUEST_LIMIT,
        "apiKey": api_key,
    }

    rows = []

    next_url = url
    next_params = params

    while next_url:

        payload = request_json(
            next_url,
            next_params,
        )

        results = payload.get(
            "results",
            [],
        )

        rows.extend(
            results
        )

        raw_next = payload.get(
            "next_url"
        )

        if raw_next:

            next_url = raw_next

            if "apiKey=" not in raw_next:
                if "?" in raw_next:
                    next_url = (
                        raw_next
                        + f"&apiKey={api_key}"
                    )
                else:
                    next_url = (
                        raw_next
                        + f"?apiKey={api_key}"
                    )

            next_params = {}

        else:
            next_url = None

        time.sleep(
            SLEEP_BETWEEN_REQUESTS
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        rows
    )

    rename_map = {
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "vw": "vwap",
        "t": "timestamp_ms",
        "n": "transactions",
    }

    df = df.rename(
        columns=rename_map
    )

    expected_cols = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
        "timestamp_ms",
        "transactions",
    ]

    for col in expected_cols:

        if col not in df.columns:
            df[col] = pd.NA

    df[
        "timestamp_utc"
    ] = pd.to_datetime(
        df[
            "timestamp_ms"
        ],
        unit="ms",
        utc=True,
    )

    eastern = (
        df[
            "timestamp_utc"
        ]
        .dt
        .tz_convert(
            "America/New_York"
        )
    )

    df[
        "trade_date"
    ] = eastern.dt.date

    minute_of_day = (
        eastern.dt.hour
        * 60
        + eastern.dt.minute
    )

    df[
        "session"
    ] = "OTHER"

    df.loc[
        (
            minute_of_day >= 240
        )
        &
        (
            minute_of_day < 570
        ),
        "session",
    ] = "PREMARKET"

    df.loc[
        (
            minute_of_day >= 570
        )
        &
        (
            minute_of_day < 960
        ),
        "session",
    ] = "RTH"

    df.loc[
        (
            minute_of_day >= 960
        )
        &
        (
            minute_of_day < 1200
        ),
        "session",
    ] = "AFTERHOURS"

    df[
        "symbol"
    ] = spec.symbol

    df[
        "timeframe"
    ] = "1m"

    df[
        "data_source"
    ] = DATA_SOURCE

    df[
        "adjusted"
    ] = True

    df = df[
        [
            "symbol",
            "trade_date",
            "timestamp_utc",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "vwap",
            "transactions",
            "session",
            "timeframe",
            "data_source",
            "adjusted",
        ]
    ]

    df = (
        df
        .sort_values(
            "timestamp_utc"
        )
        .drop_duplicates(
            subset=[
                "timestamp_utc"
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    return df


def validate_partition(
    df: pd.DataFrame,
    spec: PartitionSpec,
) -> tuple[bool, list[str]]:

    warnings = []

    if df.empty:
        return (
            False,
            [
                "No rows downloaded."
            ],
        )

    if df[
        "timestamp_utc"
    ].duplicated().any():

        return (
            False,
            [
                "Duplicate timestamps detected."
            ],
        )

    symbol_values = set(
        df[
            "symbol"
        ]
        .dropna()
        .astype(str)
        .unique()
    )

    if symbol_values != {
        spec.symbol
    }:

        return (
            False,
            [
                f"Unexpected symbols: "
                f"{symbol_values}"
            ],
        )

    min_date = min(
        df[
            "trade_date"
        ]
    )

    max_date = max(
        df[
            "trade_date"
        ]
    )

    if (
        min_date
        < spec.start_date
        or max_date
        > spec.end_date
    ):

        return (
            False,
            [
                "Rows exist outside requested "
                "date range."
            ],
        )

    trading_days = int(
        df[
            "trade_date"
        ].nunique()
    )

    rth_days = int(
        df.loc[
            df[
                "session"
            ]
            == "RTH",
            "trade_date",
        ].nunique()
    )

    if trading_days != rth_days:
        warnings.append(
            "Some trading dates lack RTH bars."
        )

    required_price_cols = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for col in required_price_cols:

        if df[col].isna().any():

            warnings.append(
                f"{col} contains null values."
            )

    return (
        True,
        warnings,
    )


def load_manifest() -> dict[str, Any]:

    if not MANIFEST_PATH.exists():

        return {
            "cache_version":
                CACHE_VERSION,

            "partitions":
                {},
        }

    with MANIFEST_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(f)


def save_manifest(
    manifest: dict[str, Any],
) -> None:

    MANIFEST_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    with MANIFEST_PATH.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            manifest,
            f,
            indent=2,
            sort_keys=True,
        )


def update_manifest(
    manifest: dict[str, Any],
    spec: PartitionSpec,
    df: pd.DataFrame,
    warnings: list[str],
) -> None:

    key = (
        f"{spec.symbol}|{spec.year}"
    )

    manifest.setdefault(
        "partitions",
        {},
    )

    manifest[
        "partitions"
    ][
        key
    ] = {
        "symbol":
            spec.symbol,

        "year":
            spec.year,

        "start_date":
            spec.start_date.isoformat(),

        "end_date":
            spec.end_date.isoformat(),

        "output_path":
            str(
                spec.output_path
            ),

        "row_n":
            int(
                len(df)
            ),

        "trade_date_n":
            int(
                df[
                    "trade_date"
                ].nunique()
            ),

        "rth_date_n":
            int(
                df.loc[
                    df[
                        "session"
                    ]
                    == "RTH",
                    "trade_date",
                ].nunique()
            ),

        "earliest_date":
            str(
                min(
                    df[
                        "trade_date"
                    ]
                )
            ),

        "latest_date":
            str(
                max(
                    df[
                        "trade_date"
                    ]
                )
            ),

        "adjusted":
            True,

        "data_source":
            DATA_SOURCE,

        "timeframe":
            "1m",

        "cache_version":
            CACHE_VERSION,

        "validation":
            (
                "PASS"
                if not warnings
                else "PASS_WITH_WARNINGS"
            ),

        "warnings":
            warnings,

        "updated_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }


# =============================================================================
# MAIN
# =============================================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Standalone DIA downloader for "
            "Second 1M Alternative C2 market "
            "regime research."
        )
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Redownload partitions even if "
            "the Parquet files already exist."
        ),
    )

    args = parser.parse_args()

    api_key = load_api_key()

    CACHE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest = load_manifest()

    partitions = build_partitions()

    print(
        "=" * 80
    )

    print(
        "SECOND 1M ALTERNATIVE C2 — "
        "DIA ACQUISITION"
    )

    print(
        "=" * 80
    )

    print(
        f"Cache version: "
        f"{CACHE_VERSION}"
    )

    print(
        f"Symbol:        "
        f"{SYMBOL}"
    )

    print(
        f"Range:         "
        f"{START_DATE} -> "
        f"{END_DATE}"
    )

    print(
        f"Partitions:    "
        f"{len(partitions)}"
    )

    print()

    downloaded_n = 0
    skipped_n = 0
    failed_n = 0
    total_rows = 0

    start_time = time.time()

    for i, spec in enumerate(
        partitions,
        start=1,
    ):

        print(
            f"[{i}/{len(partitions)}] "
            f"{spec.symbol} "
            f"{spec.year}"
        )

        print(
            f"Range:       "
            f"{spec.start_date} -> "
            f"{spec.end_date}"
        )

        if (
            spec.output_path.exists()
            and not args.force
        ):

            print(
                "Action:      "
                "SKIPPED_EXISTING"
            )

            skipped_n += 1

            print()

            continue

        try:

            print(
                "Downloading..."
            )

            df = download_partition(
                spec,
                api_key,
            )

            valid, warnings = (
                validate_partition(
                    df,
                    spec,
                )
            )

            if not valid:

                failed_n += 1

                print(
                    "Validation: FAIL"
                )

                for warning in warnings:

                    print(
                        f"  - {warning}"
                    )

                print()

                continue

            spec.output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            df.to_parquet(
                spec.output_path,
                index=False,
            )

            update_manifest(
                manifest,
                spec,
                df,
                warnings,
            )

            save_manifest(
                manifest
            )

            downloaded_n += 1

            total_rows += len(df)

            trading_days = int(
                df[
                    "trade_date"
                ].nunique()
            )

            rth_days = int(
                df.loc[
                    df[
                        "session"
                    ]
                    == "RTH",
                    "trade_date",
                ].nunique()
            )

            print(
                "Action:      "
                "DOWNLOADED"
            )

            print(
                f"Rows:        "
                f"{len(df):,}"
            )

            print(
                f"Trading days:"
                f" {trading_days:,}"
            )

            print(
                f"RTH days:    "
                f"{rth_days:,}"
            )

            print(
                "Validation:  "
                + (
                    "PASS"
                    if not warnings
                    else "PASS_WITH_WARNINGS"
                )
            )

            for warning in warnings:

                print(
                    f"  - {warning}"
                )

            print(
                f"Output:      "
                f"{spec.output_path}"
            )

        except Exception as exc:

            failed_n += 1

            print(
                "Action:      FAILED"
            )

            print(
                f"Error:       "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

        print()

    elapsed = (
        time.time()
        - start_time
    )

    print(
        "=" * 80
    )

    print(
        "DIA ACQUISITION SUMMARY"
    )

    print(
        "=" * 80
    )

    print(
        f"Downloaded:   "
        f"{downloaded_n}"
    )

    print(
        f"Skipped:      "
        f"{skipped_n}"
    )

    print(
        f"Failed:       "
        f"{failed_n}"
    )

    print(
        f"Rows:         "
        f"{total_rows:,}"
    )

    print(
        f"Elapsed sec:  "
        f"{elapsed:.1f}"
    )

    print(
        f"Cache root:   "
        f"{CACHE_ROOT}"
    )

    print(
        f"Manifest:     "
        f"{MANIFEST_PATH}"
    )

    print()

    if failed_n == 0:

        print(
            "RESULT: PASS"
        )

    else:

        print(
            "RESULT: FAIL"
        )

        sys.exit(1)


if __name__ == "__main__":
    main()