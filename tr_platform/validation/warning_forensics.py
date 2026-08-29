from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import pandas as pd

from tr_platform.common.cache_config import MarketCacheConfig


DEFAULT_SYMBOLS = ["MNDY", "NOW", "KLAC", "BKNG", "BLK", "AXON", "URI", "REGN"]


@dataclass(frozen=True)
class DayForensics:
    symbol: str
    trade_date: str
    rth_rows: int
    first_rth_et: Optional[str]
    last_rth_et: Optional[str]
    max_gap_minutes: Optional[float]
    gap_gt_5m_count: int
    gap_gt_15m_count: int
    largest_gap_start_et: Optional[str]
    largest_gap_end_et: Optional[str]
    opening_missing_minutes: Optional[float]
    closing_missing_minutes: Optional[float]


def _analyze_day(symbol: str, trade_date, day: pd.DataFrame) -> DayForensics:
    d = day.copy()
    d["timestamp_et"] = pd.to_datetime(d["timestamp_et"])
    d = d.sort_values("timestamp_et")

    if d.empty:
        return DayForensics(
            symbol=symbol, trade_date=str(trade_date), rth_rows=0,
            first_rth_et=None, last_rth_et=None, max_gap_minutes=None,
            gap_gt_5m_count=0, gap_gt_15m_count=0,
            largest_gap_start_et=None, largest_gap_end_et=None,
            opening_missing_minutes=None, closing_missing_minutes=None,
        )

    d["prev_ts"] = d["timestamp_et"].shift(1)
    d["gap_min"] = (d["timestamp_et"] - d["prev_ts"]).dt.total_seconds() / 60.0

    valid = d.dropna(subset=["gap_min"])
    max_gap = valid["gap_min"].max() if not valid.empty else None

    gap_start = None
    gap_end = None
    if max_gap is not None and not pd.isna(max_gap):
        row = valid.loc[valid["gap_min"].idxmax()]
        gap_start = str(row["prev_ts"])
        gap_end = str(row["timestamp_et"])

    first_ts = d["timestamp_et"].iloc[0]
    last_ts = d["timestamp_et"].iloc[-1]

    # Session labels in the cache define RTH. These boundary diagnostics use
    # standard 09:30–16:00 ET clock anchors only to distinguish edge truncation
    # from internal gaps.
    open_anchor = first_ts.normalize() + pd.Timedelta(hours=9, minutes=30)
    close_anchor = last_ts.normalize() + pd.Timedelta(hours=16)

    return DayForensics(
        symbol=symbol,
        trade_date=str(trade_date),
        rth_rows=len(d),
        first_rth_et=str(first_ts),
        last_rth_et=str(last_ts),
        max_gap_minutes=None if max_gap is None or pd.isna(max_gap) else float(max_gap),
        gap_gt_5m_count=int((valid["gap_min"] > 5).sum()),
        gap_gt_15m_count=int((valid["gap_min"] > 15).sum()),
        largest_gap_start_et=gap_start,
        largest_gap_end_et=gap_end,
        opening_missing_minutes=max(0.0, (first_ts - open_anchor).total_seconds() / 60.0),
        closing_missing_minutes=max(0.0, (close_anchor - last_ts).total_seconds() / 60.0),
    )


def run_warning_forensics(
    *,
    year: int,
    symbols: list[str],
    repo_root: Optional[Path] = None,
) -> tuple[Path, Path, Path]:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]

    cfg = MarketCacheConfig.from_repo_root(repo_root)
    report_dir = cfg.cache_root / "validation"
    report_dir.mkdir(parents=True, exist_ok=True)

    all_days: list[dict] = []

    for raw_symbol in symbols:
        symbol = raw_symbol.upper().strip()
        path = cfg.symbol_year_path(symbol, year)
        if not path.exists():
            all_days.append(asdict(DayForensics(
                symbol=symbol, trade_date="FILE_MISSING", rth_rows=0,
                first_rth_et=None, last_rth_et=None, max_gap_minutes=None,
                gap_gt_5m_count=0, gap_gt_15m_count=0,
                largest_gap_start_et=None, largest_gap_end_et=None,
                opening_missing_minutes=None, closing_missing_minutes=None,
            )))
            continue

        df = pd.read_parquet(path)
        rth = df[df["session"] == "RTH"].copy()
        rth["trade_date"] = pd.to_datetime(rth["trade_date"]).dt.date

        for trade_date, day in rth.groupby("trade_date"):
            all_days.append(asdict(_analyze_day(symbol, trade_date, day)))

    detail = pd.DataFrame(all_days)

    detail_csv = report_dir / f"PMPD_112_V1_{year}_warning_forensics_daily.csv"
    detail_parquet = report_dir / f"PMPD_112_V1_{year}_warning_forensics_daily.parquet"
    summary_csv = report_dir / f"PMPD_112_V1_{year}_warning_forensics_summary.csv"

    detail.to_csv(detail_csv, index=False)
    detail.to_parquet(detail_parquet, index=False)

    valid = detail[detail["trade_date"] != "FILE_MISSING"].copy()

    summary_rows = []
    for symbol, g in valid.groupby("symbol"):
        sparse = g[g["rth_rows"] < 300]
        gaps15 = g[g["max_gap_minutes"].fillna(0) > 15]
        gaps30 = g[g["max_gap_minutes"].fillna(0) > 30]

        max_gap = g["max_gap_minutes"].max()
        worst = g.loc[g["max_gap_minutes"].idxmax()] if pd.notna(max_gap) else None

        summary_rows.append({
            "symbol": symbol,
            "rth_days": len(g),
            "median_rth_rows": float(g["rth_rows"].median()),
            "p10_rth_rows": float(g["rth_rows"].quantile(0.10)),
            "min_rth_rows": int(g["rth_rows"].min()),
            "days_lt300": len(sparse),
            "days_gap_gt15m": len(gaps15),
            "days_gap_gt30m": len(gaps30),
            "max_gap_minutes": None if pd.isna(max_gap) else float(max_gap),
            "worst_gap_date": None if worst is None else worst["trade_date"],
            "worst_gap_start_et": None if worst is None else worst["largest_gap_start_et"],
            "worst_gap_end_et": None if worst is None else worst["largest_gap_end_et"],
            "days_open_edge_gt5m": int((g["opening_missing_minutes"].fillna(0) > 5).sum()),
            "days_close_edge_gt5m": int((g["closing_missing_minutes"].fillna(0) > 5).sum()),
        })

    summary = pd.DataFrame(summary_rows).sort_values(
        ["days_gap_gt15m", "days_lt300", "max_gap_minutes"],
        ascending=False,
    )
    summary.to_csv(summary_csv, index=False)

    return detail_csv, detail_parquet, summary_csv
