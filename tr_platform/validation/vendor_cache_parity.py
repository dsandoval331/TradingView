from __future__ import annotations
from dataclasses import dataclass, asdict
from getpass import getpass
from pathlib import Path
from typing import Optional
import pandas as pd

from tr_platform.common.cache_config import MarketCacheConfig, CACHE_VERSION, NEW_YORK_TZ
from tr_platform.downloader.massive_client import MassiveClient, MassiveClientConfig
from tr_platform.downloader.partition_acquisition import normalize_massive_minute_rows

DEFAULT_CASES = [
    ("BKNG", "2025-07-24"),
    ("NOW",  "2025-06-09"),
    ("MNDY", "2025-07-24"),
    ("SPY",  "2025-07-24"),
]

@dataclass(frozen=True)
class ParityResult:
    symbol: str
    trade_date: str
    vendor_rows_day: int
    cache_rows_day: int
    vendor_rth_rows: int
    cache_rth_rows: int
    vendor_only_timestamps: int
    cache_only_timestamps: int
    common_timestamps: int
    ohlcv_mismatches: int
    max_vendor_rth_gap_minutes: Optional[float]
    max_cache_rth_gap_minutes: Optional[float]
    status: str
    notes: str

def _max_gap_minutes(df: pd.DataFrame) -> Optional[float]:
    if df.empty:
        return None
    s = pd.to_datetime(df["timestamp_et"]).sort_values()
    gap = s.diff().dt.total_seconds().div(60)
    m = gap.max()
    return None if pd.isna(m) else float(m)

def _day_slice(df: pd.DataFrame, day: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    d = df.copy()
    d["timestamp_et"] = pd.to_datetime(d["timestamp_et"])
    target = pd.Timestamp(day).date()
    return d[d["timestamp_et"].dt.date == target].copy()

def compare_case(client: MassiveClient, cfg: MarketCacheConfig, symbol: str, day: str) -> ParityResult:
    symbol = symbol.upper().strip()
    raw = client.get_minute_aggs(symbol=symbol, start_date=day, end_date=day, adjusted=False)
    vendor = normalize_massive_minute_rows(symbol, raw, CACHE_VERSION)
    vendor = _day_slice(vendor, day)

    cache_path = cfg.symbol_year_path(symbol, int(day[:4]))
    if not cache_path.exists():
        return ParityResult(symbol, day, len(vendor), 0, 0, 0, 0, 0, 0, 0,
                            None, None, "FAIL", f"cache file missing: {cache_path}")

    cache = _day_slice(pd.read_parquet(cache_path), day)

    vendor_rth = vendor[vendor["session"] == "RTH"].copy()
    cache_rth = cache[cache["session"] == "RTH"].copy()

    v = vendor_rth.set_index("timestamp_ms")
    c = cache_rth.set_index("timestamp_ms")
    vi, ci = set(v.index), set(c.index)
    common = sorted(vi & ci)

    mismatches = 0
    for ts in common:
        vr, cr = v.loc[ts], c.loc[ts]
        # Exact comparison is appropriate: both originate from the same vendor
        # aggregate endpoint and canonical normalization.
        for col in ["open", "high", "low", "close", "volume"]:
            if pd.isna(vr[col]) and pd.isna(cr[col]):
                continue
            if vr[col] != cr[col]:
                mismatches += 1
                break

    vendor_only = len(vi - ci)
    cache_only = len(ci - vi)

    status = "PASS"
    notes = "Vendor and cache RTH timestamps/OHLCV match."
    if vendor_only or cache_only or mismatches:
        status = "FAIL"
        notes = (
            f"parity difference: vendor_only={vendor_only}, "
            f"cache_only={cache_only}, ohlcv_mismatches={mismatches}"
        )

    return ParityResult(
        symbol=symbol, trade_date=day,
        vendor_rows_day=len(vendor), cache_rows_day=len(cache),
        vendor_rth_rows=len(vendor_rth), cache_rth_rows=len(cache_rth),
        vendor_only_timestamps=vendor_only, cache_only_timestamps=cache_only,
        common_timestamps=len(common), ohlcv_mismatches=mismatches,
        max_vendor_rth_gap_minutes=_max_gap_minutes(vendor_rth),
        max_cache_rth_gap_minutes=_max_gap_minutes(cache_rth),
        status=status, notes=notes,
    )

def run_vendor_cache_parity(*, api_key: str, repo_root: Optional[Path] = None):
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]
    cfg = MarketCacheConfig.from_repo_root(repo_root)
    client = MassiveClient(MassiveClientConfig(api_key=api_key, requests_per_minute=4.0))
    results = [compare_case(client, cfg, s, d) for s, d in DEFAULT_CASES]
    out = cfg.cache_root / "validation"
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "PMPD_112_V1_2025_vendor_cache_parity.csv"
    pd.DataFrame([asdict(x) for x in results]).to_csv(csv_path, index=False)
    return results, csv_path

def prompt_and_run(repo_root: Optional[Path] = None):
    key = getpass("Enter your Massive API key: ").strip()
    if not key:
        raise ValueError("Massive API key cannot be blank.")
    return run_vendor_cache_parity(api_key=key, repo_root=repo_root)
