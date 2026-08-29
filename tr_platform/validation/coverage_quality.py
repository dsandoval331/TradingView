from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import pandas as pd

from tr_platform.common.cache_config import MarketCacheConfig
from tr_platform.universe.pmpd_universe import load_validated_universe


@dataclass(frozen=True)
class CoverageAudit:
    symbol: str
    year: int
    status: str
    trading_days: int
    rth_days: int
    pre_days: int
    ah_days: int
    total_rows: int
    rth_rows: int
    pre_rows: int
    ah_rows: int
    rth_days_below_300: int
    rth_days_below_350: int
    rth_days_at_least_380: int
    max_rth_gap_minutes: Optional[float]
    days_with_rth_gap_gt_5m: int
    days_with_rth_gap_gt_15m: int
    first_trade_date: Optional[str]
    last_trade_date: Optional[str]
    issues: str


@dataclass(frozen=True)
class CoverageSummary:
    year: int
    expected_partitions: int
    audited_partitions: int
    pass_count: int
    warn_count: int
    fail_count: int
    min_trading_days: int
    max_trading_days: int
    median_trading_days: float
    research_ready_candidate: bool
    report_csv: str
    report_parquet: str


def _rth_gap_stats(rth: pd.DataFrame) -> tuple[Optional[float], int, int]:
    if rth.empty:
        return None, 0, 0

    work = rth[["trade_date", "timestamp_et"]].copy()
    work["timestamp_et"] = pd.to_datetime(work["timestamp_et"])
    work = work.sort_values(["trade_date", "timestamp_et"])
    work["gap_min"] = (
        work.groupby("trade_date")["timestamp_et"]
        .diff()
        .dt.total_seconds()
        .div(60.0)
    )

    max_gap = work["gap_min"].max()
    by_day = work.groupby("trade_date")["gap_min"].max()

    return (
        None if pd.isna(max_gap) else float(max_gap),
        int((by_day > 5).sum()),
        int((by_day > 15).sum()),
    )


def audit_symbol_year(
    *,
    symbol: str,
    year: int,
    cfg: MarketCacheConfig,
) -> CoverageAudit:
    symbol = symbol.upper().strip()
    path = cfg.symbol_year_path(symbol, year)

    if not path.exists():
        return CoverageAudit(
            symbol=symbol, year=year, status="FAIL",
            trading_days=0, rth_days=0, pre_days=0, ah_days=0,
            total_rows=0, rth_rows=0, pre_rows=0, ah_rows=0,
            rth_days_below_300=0, rth_days_below_350=0,
            rth_days_at_least_380=0, max_rth_gap_minutes=None,
            days_with_rth_gap_gt_5m=0, days_with_rth_gap_gt_15m=0,
            first_trade_date=None, last_trade_date=None,
            issues="file_missing",
        )

    df = pd.read_parquet(path)

    required = {"trade_date", "timestamp_et", "session"}
    missing = required - set(df.columns)
    if missing:
        return CoverageAudit(
            symbol=symbol, year=year, status="FAIL",
            trading_days=0, rth_days=0, pre_days=0, ah_days=0,
            total_rows=len(df), rth_rows=0, pre_rows=0, ah_rows=0,
            rth_days_below_300=0, rth_days_below_350=0,
            rth_days_at_least_380=0, max_rth_gap_minutes=None,
            days_with_rth_gap_gt_5m=0, days_with_rth_gap_gt_15m=0,
            first_trade_date=None, last_trade_date=None,
            issues="missing_columns=" + ",".join(sorted(missing)),
        )

    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

    rth = df[df["session"] == "RTH"].copy()
    pre = df[df["session"] == "PRE"].copy()
    ah = df[df["session"] == "AH"].copy()

    trading_days = int(df["trade_date"].nunique())
    rth_days = int(rth["trade_date"].nunique())
    pre_days = int(pre["trade_date"].nunique())
    ah_days = int(ah["trade_date"].nunique())

    rth_counts = rth.groupby("trade_date").size()
    rth_days_below_300 = int((rth_counts < 300).sum())
    rth_days_below_350 = int((rth_counts < 350).sum())
    rth_days_at_least_380 = int((rth_counts >= 380).sum())

    max_gap, gap5, gap15 = _rth_gap_stats(rth)

    issues: list[str] = []
    status = "PASS"

    # Coverage gate: a normal full-year US equity partition should have broad
    # RTH calendar coverage. We use tolerant thresholds here because IPOs,
    # halts, corporate actions, and instrument-specific history can be valid.
    if rth_days == 0:
        status = "FAIL"
        issues.append("no_rth_days")
    elif rth_days < 200:
        status = "WARN"
        issues.append(f"low_rth_day_count={rth_days}")

    if trading_days and rth_days < trading_days - 5:
        status = "WARN" if status != "FAIL" else status
        issues.append(f"rth_days_vs_trading_days={rth_days}/{trading_days}")

    if rth_days and rth_days_below_300 > max(5, int(rth_days * 0.05)):
        status = "WARN" if status != "FAIL" else status
        issues.append(f"many_sparse_rth_days_lt300={rth_days_below_300}")

    if gap15 > max(5, int(rth_days * 0.05)):
        status = "WARN" if status != "FAIL" else status
        issues.append(f"many_days_gap_gt15m={gap15}")

    dates = sorted(df["trade_date"].dropna().unique())
    first_date = str(dates[0]) if dates else None
    last_date = str(dates[-1]) if dates else None

    return CoverageAudit(
        symbol=symbol,
        year=year,
        status=status,
        trading_days=trading_days,
        rth_days=rth_days,
        pre_days=pre_days,
        ah_days=ah_days,
        total_rows=len(df),
        rth_rows=len(rth),
        pre_rows=len(pre),
        ah_rows=len(ah),
        rth_days_below_300=rth_days_below_300,
        rth_days_below_350=rth_days_below_350,
        rth_days_at_least_380=rth_days_at_least_380,
        max_rth_gap_minutes=max_gap,
        days_with_rth_gap_gt_5m=gap5,
        days_with_rth_gap_gt_15m=gap15,
        first_trade_date=first_date,
        last_trade_date=last_date,
        issues="; ".join(issues),
    )


def audit_universe_coverage(
    *,
    year: int,
    repo_root: Optional[Path] = None,
) -> CoverageSummary:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]

    members = load_validated_universe(repo_root)
    symbols = [m.symbol for m in members]

    cfg = MarketCacheConfig.from_repo_root(repo_root)
    cfg.ensure_directories()

    rows = [
        audit_symbol_year(symbol=s, year=year, cfg=cfg)
        for s in symbols
    ]
    df = pd.DataFrame([asdict(r) for r in rows])

    report_dir = cfg.cache_root / "validation"
    report_dir.mkdir(parents=True, exist_ok=True)

    csv_path = report_dir / f"PMPD_112_V1_{year}_coverage_audit.csv"
    parquet_path = report_dir / f"PMPD_112_V1_{year}_coverage_audit.parquet"

    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)

    pass_count = int((df["status"] == "PASS").sum())
    warn_count = int((df["status"] == "WARN").sum())
    fail_count = int((df["status"] == "FAIL").sum())

    day_counts = df["rth_days"]
    return CoverageSummary(
        year=year,
        expected_partitions=len(symbols),
        audited_partitions=len(df),
        pass_count=pass_count,
        warn_count=warn_count,
        fail_count=fail_count,
        min_trading_days=int(day_counts.min()) if len(day_counts) else 0,
        max_trading_days=int(day_counts.max()) if len(day_counts) else 0,
        median_trading_days=float(day_counts.median()) if len(day_counts) else 0.0,
        research_ready_candidate=(
            len(df) == 112 and fail_count == 0 and warn_count == 0
        ),
        report_csv=str(csv_path),
        report_parquet=str(parquet_path),
    )
