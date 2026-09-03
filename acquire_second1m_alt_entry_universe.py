from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from typing import Optional

import pandas as pd

from tr_platform.common.cache_config import (
    NEW_YORK_TZ,
    classify_session,
)
from tr_platform.downloader.massive_client import (
    MassiveClient,
    MassiveClientConfig,
)
from tr_platform.universe.pmpd_universe import (
    EXPECTED_TOTAL,
    get_set_members,
)


# ============================================================
# ALTERNATIVE C2 CACHE CONTRACT
# ============================================================

CACHE_VERSION = "SECOND1M_ALT_ENTRY_CACHE_V1"
SOURCE_NAME = "massive_1m"
TIMEFRAME = "1m"
ADJUSTED = True

RESEARCH_START = "2025-05-23"
RESEARCH_END = "2026-08-27"

REQUESTS_PER_MINUTE = 4.0
MASSIVE_LIMIT = 50_000

# Keep this cache completely separate from MARKET_CACHE_V1.
CACHE_DIR_NAME = "second1m_alt_entry_cache_v1"


# ============================================================
# RESULT OBJECT
# ============================================================

@dataclass(frozen=True)
class AcquisitionResult:
    symbol: str
    year: int
    requested_start: str
    requested_end: str
    action: str
    row_count: int
    trading_days: int
    rth_days: int
    output_path: str
    validation_status: str
    error: Optional[str] = None


# ============================================================
# PATHS
# ============================================================

def repo_root() -> Path:
    return Path(__file__).resolve().parent


def cache_root(root: Path) -> Path:
    return (
        root
        / "data"
        / CACHE_DIR_NAME
    )


def partitions_root(root: Path) -> Path:
    return cache_root(root) / "partitions"


def manifests_root(root: Path) -> Path:
    return cache_root(root) / "manifests"


def manifest_path(root: Path) -> Path:
    return (
        manifests_root(root)
        / "alt_entry_manifest.json"
    )


def partition_path(
    root: Path,
    symbol: str,
    year: int,
) -> Path:
    return (
        partitions_root(root)
        / symbol.upper()
        / f"{symbol.upper()}_{year}.parquet"
    )


# ============================================================
# DATE RANGES
# ============================================================

def research_ranges() -> list[tuple[int, str, str]]:
    return [
        (
            2025,
            "2025-05-23",
            "2025-12-31",
        ),
        (
            2026,
            "2026-01-01",
            "2026-08-27",
        ),
    ]


# ============================================================
# UNIVERSE
# ============================================================

def load_research_symbols(
    root: Path,
) -> list[str]:

    symbols: list[str] = []

    for set_number in range(1, 5):

        members = get_set_members(
            root,
            set_number,
        )

        symbols.extend(
            member.symbol
            for member in members
        )

    unique_symbols = sorted(
        set(symbols)
    )

    if len(symbols) != EXPECTED_TOTAL:
        raise RuntimeError(
            "Unexpected universe member count. "
            f"Expected {EXPECTED_TOTAL}, "
            f"found {len(symbols)}."
        )

    if len(unique_symbols) != EXPECTED_TOTAL:
        raise RuntimeError(
            "Universe contains duplicate symbols. "
            f"Expected {EXPECTED_TOTAL} unique, "
            f"found {len(unique_symbols)}."
        )

    return unique_symbols


# ============================================================
# MANIFEST
# ============================================================

def load_manifest(
    path: Path,
) -> dict:

    if not path.exists():
        return {
            "cache_version": CACHE_VERSION,
            "source": SOURCE_NAME,
            "timeframe": TIMEFRAME,
            "adjusted": ADJUSTED,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "partitions": {},
        }

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    if (
        data.get("cache_version")
        != CACHE_VERSION
    ):
        raise RuntimeError(
            "Manifest cache-version mismatch."
        )

    if data.get("adjusted") is not True:
        raise RuntimeError(
            "Manifest adjusted flag is not TRUE."
        )

    return data


def write_manifest(
    path: Path,
    manifest: dict,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest["updated_at"] = utc_now()

    tmp = path.with_suffix(".tmp.json")

    with tmp.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            manifest,
            f,
            indent=2,
            sort_keys=True,
        )

    tmp.replace(path)


def manifest_key(
    symbol: str,
    year: int,
) -> str:
    return f"{symbol.upper()}|{year}"


# ============================================================
# HELPERS
# ============================================================

def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def normalize_rows(
    symbol: str,
    rows: list[dict],
) -> pd.DataFrame:

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).copy()

    df = df.rename(
        columns={
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "vw": "vwap",
            "n": "transactions",
            "t": "timestamp_ms",
        }
    )

    required = [
        "timestamp_ms",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    missing = [
        c
        for c in required
        if c not in df.columns
    ]

    if missing:
        raise RuntimeError(
            "Massive response missing "
            f"required columns: {missing}"
        )

    if "vwap" not in df.columns:
        df["vwap"] = pd.NA

    if "transactions" not in df.columns:
        df["transactions"] = pd.NA

    df["symbol"] = (
        symbol
        .upper()
        .strip()
    )

    df["timestamp_utc"] = (
        pd.to_datetime(
            df["timestamp_ms"],
            unit="ms",
            utc=True,
        )
    )

    df["timestamp_et"] = (
        df["timestamp_utc"]
        .dt
        .tz_convert(
            NEW_YORK_TZ
        )
    )

    df["trade_date"] = (
        df["timestamp_et"]
        .dt
        .date
    )

    df["session"] = [
        classify_session(
            ts.hour,
            ts.minute,
        )
        for ts
        in df["timestamp_et"]
    ]

    df["timeframe"] = TIMEFRAME
    df["source"] = SOURCE_NAME
    df["adjusted"] = ADJUSTED
    df["cache_version"] = (
        CACHE_VERSION
    )

    columns = [
        "symbol",
        "timestamp_utc",
        "timestamp_et",
        "trade_date",

        "open",
        "high",
        "low",
        "close",

        "volume",
        "vwap",
        "transactions",
        "timestamp_ms",

        "session",
        "timeframe",
        "source",
        "adjusted",
        "cache_version",
    ]

    df = (
        df[columns]
        .sort_values(
            "timestamp_utc"
        )
        .reset_index(
            drop=True
        )
    )

    return df


# ============================================================
# VALIDATION
# ============================================================

def validate_frame(
    df: pd.DataFrame,
    requested_start: str,
    requested_end: str,
) -> dict:

    if df.empty:
        return {
            "validation_status":
                "FAIL_EMPTY",
            "row_count": 0,
            "duplicate_count": 0,
            "invalid_ohlc_count": 0,
            "wrong_trade_date_count": 0,
            "out_of_range_count": 0,
            "trading_days": 0,
            "rth_days": 0,
            "premarket_days": 0,
            "afterhours_days": 0,
            "opening_complete_days": 0,
            "missing_0930_days": 0,
            "missing_0931_days": 0,
            "missing_0932_days": 0,
        }

    duplicate_count = int(
        df.duplicated(
            [
                "symbol",
                "timestamp_utc",
            ]
        ).sum()
    )

    invalid_ohlc_count = int(
        (
            (
                df["high"]
                <
                df[
                    [
                        "open",
                        "close",
                        "low",
                    ]
                ].max(axis=1)
            )
            |
            (
                df["low"]
                >
                df[
                    [
                        "open",
                        "close",
                        "high",
                    ]
                ].min(axis=1)
            )
        ).sum()
    )

    calculated_trade_date = (
        df["timestamp_utc"]
        .dt
        .tz_convert(
            NEW_YORK_TZ
        )
        .dt
        .date
    )

    wrong_trade_date_count = int(
        (
            calculated_trade_date
            != df["trade_date"]
        ).sum()
    )

    start_date = pd.Timestamp(
        requested_start
    ).date()

    end_date = pd.Timestamp(
        requested_end
    ).date()

    out_of_range_count = int(
        (
            (df["trade_date"] < start_date)
            |
            (df["trade_date"] > end_date)
        ).sum()
    )

    trading_days = int(
        df["trade_date"]
        .nunique()
    )

    rth_days = int(
        df.loc[
            df["session"] == "RTH",
            "trade_date",
        ].nunique()
    )

    premarket_days = int(
        df.loc[
            df["session"] == "PRE",
            "trade_date",
        ].nunique()
    )

    afterhours_days = int(
        df.loc[
            df["session"] == "AH",
            "trade_date",
        ].nunique()
    )

    rth = df.loc[
        df["session"] == "RTH"
    ].copy()

    if rth.empty:
        opening_complete_days = 0
        missing_0930_days = 0
        missing_0931_days = 0
        missing_0932_days = 0

    else:
        rth["_time_et"] = (
            rth["timestamp_et"]
            .dt
            .time
        )

        by_day = (
            rth.groupby(
                "trade_date"
            )["_time_et"]
            .apply(set)
        )

        t0930 = pd.Timestamp(
            "09:30"
        ).time()

        t0931 = pd.Timestamp(
            "09:31"
        ).time()

        t0932 = pd.Timestamp(
            "09:32"
        ).time()

        missing_0930_days = sum(
            t0930 not in times
            for times in by_day
        )

        missing_0931_days = sum(
            t0931 not in times
            for times in by_day
        )

        missing_0932_days = sum(
            t0932 not in times
            for times in by_day
        )

        opening_complete_days = sum(
            (
                t0930 in times
                and t0931 in times
                and t0932 in times
            )
            for times in by_day
        )

    status = "PASS"

    if (
        duplicate_count > 0
        or invalid_ohlc_count > 0
        or wrong_trade_date_count > 0
        or out_of_range_count > 0
    ):
        status = "FAIL"

    elif (
        missing_0930_days > 0
        or missing_0931_days > 0
        or missing_0932_days > 0
    ):
        status = (
            "PASS_WITH_WARNINGS"
        )

    return {
        "validation_status":
            status,

        "row_count":
            int(len(df)),

        "duplicate_count":
            duplicate_count,

        "invalid_ohlc_count":
            invalid_ohlc_count,

        "wrong_trade_date_count":
            wrong_trade_date_count,

        "out_of_range_count":
            out_of_range_count,

        "trading_days":
            trading_days,

        "rth_days":
            rth_days,

        "premarket_days":
            premarket_days,

        "afterhours_days":
            afterhours_days,

        "opening_complete_days":
            int(
                opening_complete_days
            ),

        "missing_0930_days":
            int(
                missing_0930_days
            ),

        "missing_0931_days":
            int(
                missing_0931_days
            ),

        "missing_0932_days":
            int(
                missing_0932_days
            ),
    }


# ============================================================
# SAFE PARQUET WRITE
# ============================================================

def atomic_write(
    df: pd.DataFrame,
    output_path: Path,
) -> None:

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp_path = (
        output_path
        .with_suffix(
            ".tmp.parquet"
        )
    )

    df.to_parquet(
        tmp_path,
        index=False,
    )

    check = pd.read_parquet(
        tmp_path
    )

    if len(check) != len(df):
        tmp_path.unlink(
            missing_ok=True
        )

        raise RuntimeError(
            "Parquet read-back "
            "row mismatch."
        )

    if (
        check["timestamp_utc"]
        .nunique()
        !=
        df["timestamp_utc"]
        .nunique()
    ):
        tmp_path.unlink(
            missing_ok=True
        )

        raise RuntimeError(
            "Parquet timestamp "
            "uniqueness mismatch."
        )

    tmp_path.replace(
        output_path
    )


# ============================================================
# COMPLETENESS
# ============================================================

def partition_complete(
    *,
    manifest: dict,
    symbol: str,
    year: int,
    requested_start: str,
    requested_end: str,
    output_path: Path,
) -> bool:

    key = manifest_key(
        symbol,
        year,
    )

    item = (
        manifest
        .get(
            "partitions",
            {},
        )
        .get(key)
    )

    if not item:
        return False

    return (
        item.get(
            "download_status"
        )
        == "DOWNLOADED"

        and item.get(
            "validation_status"
        )
        in {
            "PASS",
            "PASS_WITH_WARNINGS",
        }

        and item.get(
            "requested_start"
        )
        == requested_start

        and item.get(
            "requested_end"
        )
        == requested_end

        and item.get(
            "adjusted"
        )
        is True

        and item.get(
            "cache_version"
        )
        == CACHE_VERSION

        and output_path.exists()
    )


# ============================================================
# ACQUIRE ONE PARTITION
# ============================================================

def acquire_partition(
    *,
    client: MassiveClient,
    root: Path,
    manifest: dict,
    symbol: str,
    year: int,
    requested_start: str,
    requested_end: str,
    force: bool,
) -> AcquisitionResult:

    symbol = (
        symbol
        .upper()
        .strip()
    )

    output_path = (
        partition_path(
            root,
            symbol,
            year,
        )
    )

    key = manifest_key(
        symbol,
        year,
    )

    if (
        not force
        and partition_complete(
            manifest=manifest,
            symbol=symbol,
            year=year,
            requested_start=
                requested_start,
            requested_end=
                requested_end,
            output_path=
                output_path,
        )
    ):
        item = (
            manifest[
                "partitions"
            ][key]
        )

        return AcquisitionResult(
            symbol=symbol,
            year=year,
            requested_start=
                requested_start,
            requested_end=
                requested_end,
            action=
                "SKIPPED_COMPLETE",
            row_count=int(
                item.get(
                    "row_count",
                    0,
                )
            ),
            trading_days=int(
                item.get(
                    "trading_days",
                    0,
                )
            ),
            rth_days=int(
                item.get(
                    "rth_days",
                    0,
                )
            ),
            output_path=str(
                output_path
            ),
            validation_status=str(
                item.get(
                    "validation_status",
                )
            ),
        )

    existing = (
        manifest
        .get(
            "partitions",
            {},
        )
        .get(key)
    )

    attempts = (
        int(
            existing.get(
                "download_attempts",
                0,
            )
        ) + 1
        if existing
        else 1
    )

    manifest[
        "partitions"
    ][key] = {
        "symbol": symbol,
        "year": year,
        "requested_start":
            requested_start,
        "requested_end":
            requested_end,
        "source":
            SOURCE_NAME,
        "timeframe":
            TIMEFRAME,
        "adjusted":
            ADJUSTED,
        "cache_version":
            CACHE_VERSION,
        "download_status":
            "PARTIAL",
        "validation_status":
            "NOT_VALIDATED",
        "download_attempts":
            attempts,
        "output_path":
            str(output_path),
        "started_at":
            utc_now(),
    }

    write_manifest(
        manifest_path(root),
        manifest,
    )

    print(
        f"Downloading "
        f"{symbol} {year}: "
        f"{requested_start} "
        f"-> {requested_end}"
    )

    try:

        rows = (
            client
            .get_minute_aggs(
                symbol=symbol,
                start_date=
                    requested_start,
                end_date=
                    requested_end,
                adjusted=True,
                limit=MASSIVE_LIMIT,
            )
        )

        df = normalize_rows(
            symbol,
            rows,
        )

        validation = (
            validate_frame(
                df,
                requested_start,
                requested_end,
            )
        )

        if (
            validation[
                "validation_status"
            ]
            == "FAIL"
        ):
            raise RuntimeError(
                "Partition validation "
                "failed: "
                + json.dumps(
                    validation,
                    sort_keys=True,
                )
            )

        if df.empty:
            raise RuntimeError(
                "Massive returned "
                "zero rows."
            )

        atomic_write(
            df,
            output_path,
        )

        item = {
            "symbol":
                symbol,

            "year":
                year,

            "requested_start":
                requested_start,

            "requested_end":
                requested_end,

            "source":
                SOURCE_NAME,

            "timeframe":
                TIMEFRAME,

            "adjusted":
                ADJUSTED,

            "cache_version":
                CACHE_VERSION,

            "download_status":
                "DOWNLOADED",

            "validation_status":
                validation[
                    "validation_status"
                ],

            "download_attempts":
                attempts,

            "actual_first_bar":
                (
                    df[
                        "timestamp_utc"
                    ]
                    .min()
                    .isoformat()
                ),

            "actual_last_bar":
                (
                    df[
                        "timestamp_utc"
                    ]
                    .max()
                    .isoformat()
                ),

            "row_count":
                validation[
                    "row_count"
                ],

            "trading_days":
                validation[
                    "trading_days"
                ],

            "rth_days":
                validation[
                    "rth_days"
                ],

            "premarket_days":
                validation[
                    "premarket_days"
                ],

            "afterhours_days":
                validation[
                    "afterhours_days"
                ],

            "opening_complete_days":
                validation[
                    "opening_complete_days"
                ],

            "missing_0930_days":
                validation[
                    "missing_0930_days"
                ],

            "missing_0931_days":
                validation[
                    "missing_0931_days"
                ],

            "missing_0932_days":
                validation[
                    "missing_0932_days"
                ],

            "duplicate_count":
                validation[
                    "duplicate_count"
                ],

            "invalid_ohlc_count":
                validation[
                    "invalid_ohlc_count"
                ],

            "wrong_trade_date_count":
                validation[
                    "wrong_trade_date_count"
                ],

            "out_of_range_count":
                validation[
                    "out_of_range_count"
                ],

            "output_path":
                str(output_path),

            "file_size_bytes":
                output_path
                .stat()
                .st_size,

            "completed_at":
                utc_now(),
        }

        manifest[
            "partitions"
        ][key] = item

        write_manifest(
            manifest_path(root),
            manifest,
        )

        return AcquisitionResult(
            symbol=symbol,
            year=year,
            requested_start=
                requested_start,
            requested_end=
                requested_end,
            action="DOWNLOADED",
            row_count=
                validation[
                    "row_count"
                ],
            trading_days=
                validation[
                    "trading_days"
                ],
            rth_days=
                validation[
                    "rth_days"
                ],
            output_path=
                str(output_path),
            validation_status=
                validation[
                    "validation_status"
                ],
        )

    except Exception as exc:

        manifest[
            "partitions"
        ][key] = {
            "symbol":
                symbol,

            "year":
                year,

            "requested_start":
                requested_start,

            "requested_end":
                requested_end,

            "source":
                SOURCE_NAME,

            "timeframe":
                TIMEFRAME,

            "adjusted":
                ADJUSTED,

            "cache_version":
                CACHE_VERSION,

            "download_status":
                "FAILED",

            "validation_status":
                "FAIL",

            "download_attempts":
                attempts,

            "output_path":
                str(output_path),

            "failed_at":
                utc_now(),

            "error":
                f"{type(exc).__name__}: "
                f"{exc}",
        }

        write_manifest(
            manifest_path(root),
            manifest,
        )

        return AcquisitionResult(
            symbol=symbol,
            year=year,
            requested_start=
                requested_start,
            requested_end=
                requested_end,
            action="FAILED",
            row_count=0,
            trading_days=0,
            rth_days=0,
            output_path=
                str(output_path),
            validation_status="FAIL",
            error=(
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        )


# ============================================================
# PLAN
# ============================================================

def build_plan(
    symbols: list[str],
) -> list[tuple[str, int, str, str]]:

    plan = []

    for symbol in symbols:

        for (
            year,
            start,
            end,
        ) in research_ranges():

            plan.append(
                (
                    symbol,
                    year,
                    start,
                    end,
                )
            )

    return plan


def print_plan(
    plan: list[
        tuple[
            str,
            int,
            str,
            str,
        ]
    ],
    manifest: dict,
    root: Path,
) -> None:

    complete = 0
    needs_download = 0

    print()
    print("=" * 80)
    print(
        "SECOND 1M ALTERNATIVE ENTRY "
        "ACQUISITION PLAN"
    )
    print("=" * 80)

    print(
        f"Cache version:  "
        f"{CACHE_VERSION}"
    )

    print(
        f"Adjusted:       "
        f"{ADJUSTED}"
    )

    print(
        f"Partitions:     "
        f"{len(plan)}"
    )

    print()

    for (
        symbol,
        year,
        start,
        end,
    ) in plan:

        output = partition_path(
            root,
            symbol,
            year,
        )

        is_complete = (
            partition_complete(
                manifest=manifest,
                symbol=symbol,
                year=year,
                requested_start=start,
                requested_end=end,
                output_path=output,
            )
        )

        status = (
            "COMPLETE"
            if is_complete
            else "NEEDS_DOWNLOAD"
        )

        if is_complete:
            complete += 1
        else:
            needs_download += 1

        print(
            f"{symbol:<7} "
            f"{year} "
            f"{status:<14} "
            f"{start} -> {end}"
        )

    print()
    print(
        f"Already complete: "
        f"{complete}"
    )

    print(
        f"Need download:     "
        f"{needs_download}"
    )


# ============================================================
# CLI
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Acquire adjusted Massive 1m "
            "history for Alternative C2 "
            "Entry Architecture research."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Show acquisition plan only. "
            "No Massive API calls."
        ),
    )

    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help=(
            "Acquire only one symbol. "
            "Example: --symbol AAPL"
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Redownload already complete "
            "partitions."
        ),
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help=(
            "Continue after a partition "
            "download failure."
        ),
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main():

    args = parse_args()

    root = repo_root()

    symbols = load_research_symbols(
        root
    )

    if args.symbol:

        selected = (
            args.symbol
            .upper()
            .strip()
        )

        if selected not in symbols:
            raise RuntimeError(
                f"{selected} is not in "
                "the authoritative "
                "PMPD 112 universe."
            )

        symbols = [selected]

    manifest_file = (
        manifest_path(root)
    )

    manifest = load_manifest(
        manifest_file
    )

    plan = build_plan(
        symbols
    )

    print_plan(
        plan,
        manifest,
        root,
    )

    if args.dry_run:

        print()
        print(
            "DRY RUN ONLY. "
            "No Massive API calls "
            "were made."
        )

        return

    api_key = (
        os.environ
        .get(
            "MASSIVE_API_KEY"
        )
    )

    if not api_key:

        api_key = getpass(
            "Enter Massive API key: "
        ).strip()

    if not api_key:
        raise RuntimeError(
            "Massive API key "
            "was not provided."
        )

    client = MassiveClient(
        MassiveClientConfig(
            api_key=api_key,
            requests_per_minute=
                REQUESTS_PER_MINUTE,
        )
    )

    results: list[
        AcquisitionResult
    ] = []

    start_time = time.time()

    for index, (
        symbol,
        year,
        requested_start,
        requested_end,
    ) in enumerate(
        plan,
        start=1,
    ):

        print()
        print(
            f"[{index}/{len(plan)}] "
            f"{symbol} {year}"
        )

        result = acquire_partition(
            client=client,
            root=root,
            manifest=manifest,
            symbol=symbol,
            year=year,
            requested_start=
                requested_start,
            requested_end=
                requested_end,
            force=args.force,
        )

        results.append(
            result
        )

        print(
            f"Action:      "
            f"{result.action}"
        )

        print(
            f"Rows:        "
            f"{result.row_count:,}"
        )

        print(
            f"Trading days:"
            f" {result.trading_days:,}"
        )

        print(
            f"RTH days:    "
            f"{result.rth_days:,}"
        )

        print(
            f"Validation:  "
            f"{result.validation_status}"
        )

        if result.error:

            print(
                f"Error:       "
                f"{result.error}"
            )

            if not (
                args
                .continue_on_error
            ):
                raise SystemExit(
                    1
                )

    elapsed = (
        time.time()
        - start_time
    )

    downloaded = sum(
        r.action == "DOWNLOADED"
        for r in results
    )

    skipped = sum(
        r.action
        == "SKIPPED_COMPLETE"
        for r in results
    )

    failed = sum(
        r.action == "FAILED"
        for r in results
    )

    total_rows = sum(
        r.row_count
        for r in results
        if r.action
        == "DOWNLOADED"
    )

    print()
    print("=" * 80)
    print(
        "ALTERNATIVE ENTRY "
        "ACQUISITION SUMMARY"
    )
    print("=" * 80)

    print(
        f"Total partitions: "
        f"{len(results)}"
    )

    print(
        f"Downloaded:       "
        f"{downloaded}"
    )

    print(
        f"Skipped complete: "
        f"{skipped}"
    )

    print(
        f"Failed:           "
        f"{failed}"
    )

    print(
        f"Downloaded rows:  "
        f"{total_rows:,}"
    )

    print(
        f"Elapsed seconds:  "
        f"{elapsed:,.1f}"
    )

    print(
        f"Cache root:       "
        f"{cache_root(root)}"
    )

    print(
        f"Manifest:         "
        f"{manifest_file}"
    )

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()