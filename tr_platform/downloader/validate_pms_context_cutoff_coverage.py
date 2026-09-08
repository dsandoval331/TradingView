from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


CONTEXT_SYMBOLS = [
    "SPY", "QQQ", "DIA",
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK",
    "XLP", "XLRE", "XLU", "XLV", "XLY",
]

CENTRAL_TZ = "America/Chicago"
SCAN_A_TIME = "08:00"
SCAN_B_TIME = "08:25"
PM_START_TIME = "03:00"
PM_END_TIME = "08:29"


@dataclass(frozen=True)
class CoverageResult:
    symbol: str
    year: int
    file_exists: bool
    row_count: int
    trading_days: int
    pm_days_any: int
    scan_a_days: int
    scan_b_days: int
    scan_a_pct: float | None
    scan_b_pct: float | None
    missing_scan_a_days: int
    missing_scan_b_days: int
    sparse_pm_days: int
    status: str
    notes: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def candidate_timestamp_columns(columns: Iterable[str]) -> list[str]:
    cols = list(columns)
    preferred = [
        "timestamp",
        "datetime",
        "date_time",
        "time",
        "ts",
        "window_start",
        "start_timestamp",
    ]
    found = [c for c in preferred if c in cols]
    if found:
        return found

    heuristics = []
    for c in cols:
        lc = c.lower()
        if "timestamp" in lc or "datetime" in lc or lc.endswith("_time"):
            heuristics.append(c)
    return heuristics


def parse_timestamp_series(df: pd.DataFrame) -> pd.Series:
    candidates = candidate_timestamp_columns(df.columns)
    if not candidates:
        raise ValueError(
            "No timestamp-like column found. "
            f"Available columns: {list(df.columns)}"
        )

    last_error: Exception | None = None

    for col in candidates:
        s = df[col]

        try:
            if pd.api.types.is_datetime64_any_dtype(s):
                ts = pd.to_datetime(s, errors="coerce", utc=True)
                if ts.notna().any():
                    return ts

            if pd.api.types.is_numeric_dtype(s):
                non_null = s.dropna()
                if non_null.empty:
                    continue

                sample = float(non_null.iloc[0])

                if sample > 1e17:
                    unit = "ns"
                elif sample > 1e14:
                    unit = "us"
                elif sample > 1e11:
                    unit = "ms"
                elif sample > 1e9:
                    unit = "s"
                else:
                    continue

                ts = pd.to_datetime(s, unit=unit, errors="coerce", utc=True)
                if ts.notna().any():
                    return ts

            ts = pd.to_datetime(s, errors="coerce", utc=True)
            if ts.notna().any():
                return ts

        except Exception as exc:
            last_error = exc

    raise ValueError(
        f"Unable to parse timestamp column candidates {candidates}. "
        f"Last error: {last_error}"
    )


def time_mask(local_ts: pd.Series, start_hhmm: str, end_hhmm: str) -> pd.Series:
    hhmm = local_ts.dt.strftime("%H:%M")
    return (hhmm >= start_hhmm) & (hhmm <= end_hhmm)


def exact_or_prior_minute_present(
    group: pd.DataFrame,
    cutoff_hhmm: str,
) -> bool:
    """
    Coverage rule for scanner cutoff:
    at least one PM bar exists at or before cutoff on the same trade date.

    We intentionally do NOT require an exact 08:00/08:25 trade, because thin
    sector ETFs can have sparse extended-hours prints. Missingness is measured
    separately via sparse_pm_days and bar counts.
    """
    cutoff_minutes = int(cutoff_hhmm[:2]) * 60 + int(cutoff_hhmm[3:])
    mins = group["_local_ts"].dt.hour * 60 + group["_local_ts"].dt.minute

    pm_start_minutes = 3 * 60
    valid = (mins >= pm_start_minutes) & (mins <= cutoff_minutes)
    return bool(valid.any())


def analyze_partition(path: Path, symbol: str, year: int) -> CoverageResult:
    if not path.exists():
        return CoverageResult(
            symbol=symbol,
            year=year,
            file_exists=False,
            row_count=0,
            trading_days=0,
            pm_days_any=0,
            scan_a_days=0,
            scan_b_days=0,
            scan_a_pct=None,
            scan_b_pct=None,
            missing_scan_a_days=0,
            missing_scan_b_days=0,
            sparse_pm_days=0,
            status="MISSING_FILE",
            notes=str(path),
        )

    df = pd.read_parquet(path)
    if df.empty:
        return CoverageResult(
            symbol=symbol,
            year=year,
            file_exists=True,
            row_count=0,
            trading_days=0,
            pm_days_any=0,
            scan_a_days=0,
            scan_b_days=0,
            scan_a_pct=None,
            scan_b_pct=None,
            missing_scan_a_days=0,
            missing_scan_b_days=0,
            sparse_pm_days=0,
            status="EMPTY_FILE",
            notes=str(path),
        )

    utc_ts = parse_timestamp_series(df)
    valid = utc_ts.notna()

    df = df.loc[valid].copy()
    utc_ts = utc_ts.loc[valid]

    if df.empty:
        raise ValueError(f"{symbol} {year}: no valid timestamps after parsing.")

    local_ts = utc_ts.dt.tz_convert(CENTRAL_TZ)
    df["_local_ts"] = local_ts
    df["_trade_date"] = local_ts.dt.date

    # Restrict to regular weekdays represented in the file.
    # Trading-day denominator is based on dates with any RTH observation,
    # preventing weekends/holidays from being treated as missing.
    rth_mask = time_mask(df["_local_ts"], "08:30", "15:00")
    trading_dates = set(df.loc[rth_mask, "_trade_date"].unique())

    pm_mask = time_mask(df["_local_ts"], PM_START_TIME, PM_END_TIME)
    pm_df = df.loc[pm_mask].copy()

    pm_counts = (
        pm_df.groupby("_trade_date")
        .size()
        .rename("pm_bar_count")
    )

    pm_days_any = sum(d in set(pm_counts.index) for d in trading_dates)

    scan_a_days = 0
    scan_b_days = 0
    sparse_pm_days = 0

    grouped = {
        d: g
        for d, g in pm_df.groupby("_trade_date")
        if d in trading_dates
    }

    # Sparse is intentionally descriptive, not a failure condition.
    # Fewer than 30 PM bars means there was some PM activity but coverage was thin.
    for d in trading_dates:
        g = grouped.get(d)

        if g is None or g.empty:
            continue

        if len(g) < 30:
            sparse_pm_days += 1

        if exact_or_prior_minute_present(g, SCAN_A_TIME):
            scan_a_days += 1

        if exact_or_prior_minute_present(g, SCAN_B_TIME):
            scan_b_days += 1

    trading_days = len(trading_dates)

    scan_a_pct = (
        round(100.0 * scan_a_days / trading_days, 2)
        if trading_days else None
    )
    scan_b_pct = (
        round(100.0 * scan_b_days / trading_days, 2)
        if trading_days else None
    )

    missing_scan_a = max(trading_days - scan_a_days, 0)
    missing_scan_b = max(trading_days - scan_b_days, 0)

    if trading_days == 0:
        status = "INVALID_NO_RTH_DAYS"
    elif scan_a_days == trading_days and scan_b_days == trading_days:
        status = "PASS"
    elif scan_a_days > 0 and scan_b_days > 0:
        status = "PASS_WITH_COVERAGE_GAPS"
    else:
        status = "INSUFFICIENT_PM_COVERAGE"

    notes = (
        "SCAN_A/B coverage means at least one premarket bar exists at or before "
        "the cutoff on that trading date. Sparse PM activity is reported separately "
        "and is not zero-filled or treated as neutral."
    )

    return CoverageResult(
        symbol=symbol,
        year=year,
        file_exists=True,
        row_count=len(df),
        trading_days=trading_days,
        pm_days_any=pm_days_any,
        scan_a_days=scan_a_days,
        scan_b_days=scan_b_days,
        scan_a_pct=scan_a_pct,
        scan_b_pct=scan_b_pct,
        missing_scan_a_days=missing_scan_a,
        missing_scan_b_days=missing_scan_b,
        sparse_pm_days=sparse_pm_days,
        status=status,
        notes=notes,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate PMS SCAN_A/SCAN_B cutoff coverage for canonical "
            "MARKET_CACHE_V1 1-minute Parquet partitions."
        )
    )

    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2025, 2026],
        help="Years to inspect. Default: 2025 2026",
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        default=CONTEXT_SYMBOLS,
        help="Symbols to inspect. Defaults to PMS context universe.",
    )

    parser.add_argument(
        "--cache-root",
        type=Path,
        default=None,
        help=(
            "Override MARKET_CACHE_V1 root. Default: "
            "<repo>/market_cache/MARKET_CACHE_V1"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "CSV output path. Default: "
            "<repo>/research_outputs/pms_context_cutoff_coverage.csv"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    root = repo_root()

    cache_root = (
        args.cache_root
        if args.cache_root is not None
        else root / "market_cache" / "MARKET_CACHE_V1"
    )

    output = (
        args.output
        if args.output is not None
        else root / "research_outputs" / "pms_context_cutoff_coverage.csv"
    )

    output.parent.mkdir(parents=True, exist_ok=True)

    results: list[CoverageResult] = []

    for year in args.years:
        for raw_symbol in args.symbols:
            symbol = raw_symbol.upper().strip()
            path = cache_root / "1m" / symbol / f"{year}.parquet"

            print(f"Analyzing {symbol} {year}: {path}")

            try:
                result = analyze_partition(path, symbol, year)
            except Exception as exc:
                result = CoverageResult(
                    symbol=symbol,
                    year=year,
                    file_exists=path.exists(),
                    row_count=0,
                    trading_days=0,
                    pm_days_any=0,
                    scan_a_days=0,
                    scan_b_days=0,
                    scan_a_pct=None,
                    scan_b_pct=None,
                    missing_scan_a_days=0,
                    missing_scan_b_days=0,
                    sparse_pm_days=0,
                    status="ERROR",
                    notes=f"{type(exc).__name__}: {exc}",
                )

            results.append(result)

    out_df = pd.DataFrame([r.__dict__ for r in results])

    print()
    print("=== PMS CONTEXT CUTOFF COVERAGE ===")
    print(
        out_df[
            [
                "symbol",
                "year",
                "row_count",
                "trading_days",
                "pm_days_any",
                "scan_a_days",
                "scan_a_pct",
                "scan_b_days",
                "scan_b_pct",
                "sparse_pm_days",
                "status",
            ]
        ].to_string(index=False)
    )

    print()
    print("=== STATUS COUNTS ===")
    print(out_df["status"].value_counts(dropna=False).to_string())

    out_df.to_csv(output, index=False)

    print()
    print(f"CSV written to: {output}")

    failures = out_df["status"].isin(
        ["MISSING_FILE", "EMPTY_FILE", "INVALID_NO_RTH_DAYS", "ERROR"]
    )

    if failures.any():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
