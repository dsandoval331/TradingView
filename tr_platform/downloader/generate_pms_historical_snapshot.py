from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import date, datetime, time
from pathlib import Path
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


CENTRAL_TZ = ZoneInfo("America/Chicago")
UTC_TZ = ZoneInfo("UTC")

UNIVERSE_CODE = "PMPD_112_V1"
UNIVERSE_VERSION = "V1"
FACTOR_REGISTRY_VERSION = "PMS-FR-0.1"
FEATURE_CONTRACT_VERSION = "PMS-FC-0.3"
SNAPSHOT_CONTRACT_VERSION = "PMS-SNAPSHOT-0.1"
SECTOR_MAPPING_VERSION = "PMS-SECTOR-MAP-0.1"
MARKET_CACHE_VERSION = "MARKET_CACHE_V1"

# Current technical-feature warm-up contract. This is derived from the
# longest implemented daily feature requirement in this generator:
# MACD(12,26,9) currently requires 35 completed prior RTH sessions.
REQUIRED_WARMUP_RTH_SESSIONS = 35
WARMUP_CONTRACT_VERSION = "PMS-WARMUP-0.1"

STRATEGY_FAMILIES = ["PMPD", "SECOND1M", "ORB15", "ORB_FIB"]
DIRECTIONS = ["BULLISH", "BEARISH"]

SNAPSHOT_TIMES = {
    "SCAN_A": time(8, 0),
    "SCAN_B": time(8, 25),
}

PM_START = time(3, 0)
PM_END = time(8, 29)
RTH_START = time(8, 30)
RTH_END = time(15, 0)

CONTEXT_SYMBOLS = [
    "SPY", "QQQ", "DIA",
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK",
    "XLP", "XLRE", "XLU", "XLV", "XLY",
]

PMPD_112_V1 = [
    "AAPL","ABBV","ABNB","ADBE","AMAT","AMD","AMGN","AMZN","ANET","APP","ARM","ASML",
    "AVGO","AXON","AXP","BA","BAC","BKNG","BLK","BMY","C","CAT","CEG","CMCSA","CME","CMG",
    "COIN","COP","COST","CRM","CRWD","CSCO","CVS","CVX","DASH","DDOG","DE","DELL","DIS","EOG",
    "ETN","FDX","GE","GILD","GOOG","GS","HAL","HD","HON","HOOD","IBM","INTC","ISRG","IWM",
    "JNJ","JPM","KLAC","LLY","LMT","LOW","LRCX","LULU","MA","MCD","META","MNDY","MRK","MRNA",
    "MRVL","MS","MSFT","MU","NEE","NFLX","NKE","NOW","NVDA","ORCL","OXY","PANW","PEP","PFE",
    "PLTR","PYPL","QCOM","QQQ","RBLX","REGN","RTX","SBUX","SCHW","SHOP","SLB","SNOW","SPY",
    "T","TEAM","TGT","TMO","TMUS","TQQQ","TSLA","TXN","UBER","UNH","UPS","URI","V","VRTX",
    "VZ","WMT","XOM"
]

# Point-in-time sector benchmark map. APP is handled separately below because
# it changes from XLK to XLC on 2026-08-01.
SECTOR_MAP = {}
def _assign(symbols: str, benchmark: Optional[str]) -> None:
    for s in symbols.split():
        SECTOR_MAP[s] = benchmark

_assign("AAPL ADBE AMAT AMD ANET ARM ASML AVGO CRM CRWD CSCO DDOG DELL IBM INTC KLAC LRCX MNDY MRVL MSFT MU NOW NVDA ORCL PANW PLTR QCOM SHOP SNOW TEAM TXN", "XLK")
_assign("ABBV AMGN BMY CVS GILD ISRG JNJ LLY MRK MRNA PFE REGN TMO UNH VRTX", "XLV")
_assign("ABNB AMZN BKNG CMG DASH HD LOW LULU MCD NKE SBUX TSLA", "XLY")
_assign("AXON BA CAT DE ETN FDX GE HON LMT RTX UBER UPS URI", "XLI")
_assign("AXP BAC BLK C CME COIN GS HOOD JPM MA MS PYPL SCHW V", "XLF")
_assign("CEG NEE", "XLU")
_assign("CMCSA DIS GOOG META NFLX RBLX T TMUS VZ", "XLC")
_assign("COP CVX EOG HAL OXY SLB XOM", "XLE")
_assign("COST PEP TGT WMT", "XLP")
_assign("IWM QQQ SPY TQQQ", None)

assert len(PMPD_112_V1) == 112


@dataclass
class SnapshotCandidate:
    trade_date: str
    snapshot_code: str
    snapshot_asof_utc: str
    symbol: str
    strategy_family: str
    direction: str
    eligibility_state: str
    gate_state: Optional[str]
    composite_score: Optional[float]
    raw_features_json: str
    context_states_json: str
    gate_results_json: str
    missing_data_json: str
    explanation_json: str
    lineage_json: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def timestamp_candidates(columns: Iterable[str]) -> list[str]:
    cols = list(columns)
    preferred = [
        "timestamp", "datetime", "date_time", "time",
        "ts", "window_start", "start_timestamp",
    ]
    found = [c for c in preferred if c in cols]
    if found:
        return found
    return [
        c for c in cols
        if "timestamp" in c.lower()
        or "datetime" in c.lower()
        or c.lower().endswith("_time")
    ]


def parse_timestamp_series(df: pd.DataFrame) -> pd.Series:
    candidates = timestamp_candidates(df.columns)
    if not candidates:
        raise ValueError(f"No timestamp-like column. Columns={list(df.columns)}")

    for col in candidates:
        s = df[col]
        try:
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
                    unit = None
                if unit:
                    out = pd.to_datetime(s, unit=unit, errors="coerce", utc=True)
                    if out.notna().any():
                        return out

            out = pd.to_datetime(s, errors="coerce", utc=True)
            if out.notna().any():
                return out
        except Exception:
            continue

    raise ValueError(f"Unable to parse timestamp candidates {candidates}")


def normalize_ohlcv_columns(df: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "open": ["open", "o"],
        "high": ["high", "h"],
        "low": ["low", "l"],
        "close": ["close", "c"],
        "volume": ["volume", "v"],
    }
    rename = {}
    lower_map = {c.lower(): c for c in df.columns}

    for target, options in aliases.items():
        for option in options:
            if option in lower_map:
                rename[lower_map[option]] = target
                break

    out = df.rename(columns=rename).copy()
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}. Columns={list(df.columns)}")
    return out


class PartitionStore:
    def __init__(self, cache_root: Path):
        self.cache_root = cache_root
        self._cache: dict[tuple[str, int], tuple[pd.DataFrame, Path]] = {}

    def load(self, symbol: str, year: int) -> tuple[pd.DataFrame, Path]:
        key = (symbol, year)
        if key in self._cache:
            return self._cache[key]

        path = self.cache_root / "1m" / symbol / f"{year}.parquet"
        if not path.exists():
            raise FileNotFoundError(path)

        raw = pd.read_parquet(path)
        raw = normalize_ohlcv_columns(raw)
        ts = parse_timestamp_series(raw)

        valid = ts.notna()
        df = raw.loc[valid].copy()
        ts = ts.loc[valid]

        df["_utc_ts"] = ts
        df["_local_ts"] = ts.dt.tz_convert(CENTRAL_TZ)
        df["_trade_date"] = df["_local_ts"].dt.date
        df = df.sort_values("_utc_ts").reset_index(drop=True)

        self._cache[key] = (df, path)
        return df, path

    def load_window(self, symbol: str, trade_date: date, prior_year_needed: bool = True) -> tuple[pd.DataFrame, list[Path]]:
        years = {trade_date.year}
        if prior_year_needed:
            years.add(trade_date.year - 1)

        frames = []
        paths = []
        for y in sorted(years):
            try:
                df, path = self.load(symbol, y)
                frames.append(df)
                paths.append(path)
            except FileNotFoundError:
                continue

        if not frames:
            raise FileNotFoundError(f"No partitions found for {symbol} around {trade_date}")

        return pd.concat(frames, ignore_index=True).sort_values("_utc_ts"), paths


def session_mask(local_ts: pd.Series, start: time, end: time) -> pd.Series:
    t = local_ts.dt.time
    return (t >= start) & (t <= end)


def daily_rth(df: pd.DataFrame, through_date: date) -> pd.DataFrame:
    mask = session_mask(df["_local_ts"], RTH_START, RTH_END)
    rth = df.loc[mask & (df["_trade_date"] <= through_date)].copy()
    if rth.empty:
        return pd.DataFrame()

    grouped = rth.groupby("_trade_date", sort=True)
    daily = pd.DataFrame({
        "open": grouped["open"].first(),
        "high": grouped["high"].max(),
        "low": grouped["low"].min(),
        "close": grouped["close"].last(),
        "volume": grouped["volume"].sum(),
    })
    daily.index = pd.Index(daily.index, name="trade_date")
    return daily.sort_index()


def true_range(daily: pd.DataFrame) -> pd.Series:
    prev_close = daily["close"].shift(1)
    return pd.concat([
        daily["high"] - daily["low"],
        (daily["high"] - prev_close).abs(),
        (daily["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)


def atr14(daily: pd.DataFrame) -> Optional[float]:
    if len(daily) < 15:
        return None
    tr = true_range(daily)
    val = tr.rolling(14, min_periods=14).mean().iloc[-1]
    return None if pd.isna(val) else float(val)


def rsi14(daily: pd.DataFrame) -> Optional[float]:
    if len(daily) < 15:
        return None
    delta = daily["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    g = avg_gain.iloc[-1]
    l = avg_loss.iloc[-1]
    if pd.isna(g) or pd.isna(l):
        return None
    if l == 0:
        return 100.0
    rs = g / l
    return float(100 - (100 / (1 + rs)))


def macd_12_26_9(daily: pd.DataFrame) -> dict:
    if len(daily) < 35:
        return {"macd": None, "signal": None, "histogram": None}
    close = daily["close"]
    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()
    macd = fast - slow
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return {
        "macd": float(macd.iloc[-1]),
        "signal": float(signal.iloc[-1]),
        "histogram": float(hist.iloc[-1]),
    }


def bollinger_20_2(daily: pd.DataFrame) -> dict:
    if len(daily) < 20:
        return {"mid": None, "upper": None, "lower": None, "bandwidth_pct": None}
    close = daily["close"]
    mid = close.rolling(20).mean().iloc[-1]
    std = close.rolling(20).std(ddof=0).iloc[-1]
    if pd.isna(mid) or pd.isna(std):
        return {"mid": None, "upper": None, "lower": None, "bandwidth_pct": None}
    upper = mid + 2 * std
    lower = mid - 2 * std
    bandwidth = ((upper - lower) / mid * 100) if mid else None
    return {
        "mid": float(mid),
        "upper": float(upper),
        "lower": float(lower),
        "bandwidth_pct": None if bandwidth is None else float(bandwidth),
    }


def pct_return(close: pd.Series, periods: int) -> Optional[float]:
    if len(close) <= periods:
        return None
    base = close.iloc[-1 - periods]
    last = close.iloc[-1]
    if pd.isna(base) or pd.isna(last) or base == 0:
        return None
    return float((last / base - 1) * 100)


def point_in_time_sector_benchmark(symbol: str, trade_date: date) -> Optional[str]:
    if symbol == "APP":
        return "XLK" if trade_date <= date(2026, 7, 31) else "XLC"
    return SECTOR_MAP.get(symbol)


def premarket_features(df: pd.DataFrame, trade_date: date, cutoff: time) -> dict:
    same_day = df["_trade_date"] == trade_date
    local_t = df["_local_ts"].dt.time
    pm = df.loc[
        same_day
        & (local_t >= PM_START)
        & (local_t <= cutoff)
    ].copy()

    cutoff_dt = datetime.combine(trade_date, cutoff, tzinfo=CENTRAL_TZ)
    pm_start_dt = datetime.combine(trade_date, PM_START, tzinfo=CENTRAL_TZ)
    possible_minutes = int((cutoff_dt - pm_start_dt).total_seconds() // 60) + 1

    if pm.empty:
        return {
            "bar_count": 0,
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": None,
            "range_pct": None,
            "return_pct": None,
            "last_bar_time_ct": None,
            "staleness_minutes_at_cutoff": None,
            "exact_cutoff_bar_present": False,
            "possible_pm_minutes_to_cutoff": possible_minutes,
            "observed_pm_minute_density_pct": 0.0,
            "observation_state": "MISSING",
        }

    o = float(pm["open"].iloc[0])
    h = float(pm["high"].max())
    l = float(pm["low"].min())
    c = float(pm["close"].iloc[-1])
    vol = float(pm["volume"].sum())

    last_local = pm["_local_ts"].iloc[-1]
    staleness_minutes = max(
        0.0,
        (cutoff_dt - last_local.to_pydatetime()).total_seconds() / 60.0,
    )
    exact_cutoff = bool(
        (
            (pm["_local_ts"].dt.hour == cutoff.hour)
            & (pm["_local_ts"].dt.minute == cutoff.minute)
        ).any()
    )

    # A canonical 1-minute partition has at most one bar per minute. This is
    # descriptive observation density only; it is NOT currently an eligibility
    # threshold and must not be interpreted as a score.
    density_pct = (
        float(len(pm) / possible_minutes * 100.0)
        if possible_minutes > 0
        else None
    )

    return {
        "bar_count": int(len(pm)),
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": vol,
        "range_pct": None if o == 0 else float((h - l) / o * 100),
        "return_pct": None if o == 0 else float((c / o - 1) * 100),
        "last_bar_time_ct": last_local.isoformat(),
        "staleness_minutes_at_cutoff": float(staleness_minutes),
        "exact_cutoff_bar_present": exact_cutoff,
        "possible_pm_minutes_to_cutoff": possible_minutes,
        "observed_pm_minute_density_pct": density_pct,
        "observation_state": "OBSERVED",
    }


def previous_rth_features(daily: pd.DataFrame, trade_date: date) -> dict:
    prior = daily.loc[daily.index < trade_date]
    if prior.empty:
        return {}
    last = prior.iloc[-1]
    return {
        "previous_rth_date": str(prior.index[-1]),
        "previous_rth_open": float(last["open"]),
        "previous_rth_high": float(last["high"]),
        "previous_rth_low": float(last["low"]),
        "previous_rth_close": float(last["close"]),
        "previous_rth_volume": float(last["volume"]),
    }



def history_readiness(prior: pd.DataFrame, source_paths: list[Path]) -> dict:
    observed = int(len(prior))
    first_date = None if prior.empty else str(prior.index.min())
    last_date = None if prior.empty else str(prior.index.max())
    ready = observed >= REQUIRED_WARMUP_RTH_SESSIONS

    source_years = []
    for p in source_paths:
        try:
            source_years.append(int(p.stem))
        except ValueError:
            continue

    return {
        "contract_version": WARMUP_CONTRACT_VERSION,
        "required_prior_rth_sessions": REQUIRED_WARMUP_RTH_SESSIONS,
        "observed_prior_rth_sessions": observed,
        "first_prior_rth_date": first_date,
        "last_prior_rth_date": last_date,
        "source_partition_years": sorted(set(source_years)),
        "state": "READY" if ready else "INSUFFICIENT_HISTORY",
        "ready": ready,
    }

def classify_missing(required: dict[str, object]) -> dict:
    missing = []
    for k, v in required.items():
        if v is None:
            missing.append({"feature": k, "state": "MISSING"})
        elif isinstance(v, float) and np.isnan(v):
            missing.append({"feature": k, "state": "INVALID"})
    return {
        "required_core_missing_count": len(missing),
        "items": missing,
    }


def market_context(store: PartitionStore, trade_date: date, cutoff: time) -> tuple[dict, dict]:
    values = {}
    missing = {}
    for symbol in ["SPY", "QQQ", "DIA"]:
        try:
            df, _ = store.load_window(symbol, trade_date)
            daily = daily_rth(df, trade_date)
            prior = daily.loc[daily.index < trade_date]
            pm = premarket_features(df, trade_date, cutoff)

            prev_close = float(prior["close"].iloc[-1]) if not prior.empty else None
            pm_close = pm["close"]
            ret = None
            if prev_close is not None and pm_close is not None and prev_close != 0:
                ret = float((pm_close / prev_close - 1) * 100)

            values[symbol] = {
                "premarket_return_vs_prev_close_pct": ret,
                "premarket_bar_count": pm["bar_count"],
                "last_pm_bar_time_ct": pm["last_bar_time_ct"],
            }
            missing[symbol] = "VALID" if ret is not None else "MISSING"
        except Exception as exc:
            values[symbol] = {"error": f"{type(exc).__name__}: {exc}"}
            missing[symbol] = "INVALID"
    return values, missing


def sector_context(
    store: PartitionStore,
    benchmark: Optional[str],
    trade_date: date,
    cutoff: time,
) -> tuple[dict, str]:
    if benchmark is None:
        return {
            "benchmark_symbol": None,
            "applicability": "NOT_APPLICABLE",
        }, "NOT_APPLICABLE"

    try:
        df, _ = store.load_window(benchmark, trade_date)
        daily = daily_rth(df, trade_date)
        prior = daily.loc[daily.index < trade_date]
        pm = premarket_features(df, trade_date, cutoff)

        prev_close = float(prior["close"].iloc[-1]) if not prior.empty else None
        pm_close = pm["close"]

        ret = None
        if prev_close is not None and pm_close is not None and prev_close != 0:
            ret = float((pm_close / prev_close - 1) * 100)

        state = "VALID" if ret is not None else "MISSING"
        return {
            "benchmark_symbol": benchmark,
            "premarket_return_vs_prev_close_pct": ret,
            "premarket_bar_count": pm["bar_count"],
            "last_pm_bar_time_ct": pm["last_bar_time_ct"],
        }, state

    except Exception as exc:
        return {
            "benchmark_symbol": benchmark,
            "error": f"{type(exc).__name__}: {exc}",
        }, "INVALID"


def build_symbol_features(
    store: PartitionStore,
    symbol: str,
    trade_date: date,
    cutoff: time,
) -> tuple[dict, dict, dict]:
    df, source_paths = store.load_window(symbol, trade_date)
    daily = daily_rth(df, trade_date)
    prior = daily.loc[daily.index < trade_date]

    pm = premarket_features(df, trade_date, cutoff)
    prev = previous_rth_features(daily, trade_date)
    warmup = history_readiness(prior, source_paths)

    atr = atr14(prior)
    rsi = rsi14(prior)
    macd = macd_12_26_9(prior)
    bb = bollinger_20_2(prior)

    prev_close = prev.get("previous_rth_close")
    gap_pct = None
    if prev_close is not None and pm["open"] is not None and prev_close != 0:
        gap_pct = float((pm["open"] / prev_close - 1) * 100)

    pm_range_atr = None
    if atr is not None and atr != 0 and pm["high"] is not None and pm["low"] is not None:
        pm_range_atr = float((pm["high"] - pm["low"]) / atr)

    gap_atr = None
    if atr is not None and atr != 0 and prev_close is not None and pm["open"] is not None:
        gap_atr = float((pm["open"] - prev_close) / atr)

    close = prior["close"] if not prior.empty else pd.Series(dtype=float)

    raw = {
        **prev,
        "history_readiness": warmup,
        "premarket": pm,
        "gap_pct": gap_pct,
        "gap_atr": gap_atr,
        "premarket_range_atr": pm_range_atr,
        "atr14": atr,
        "rsi14": rsi,
        "macd_12_26_9": macd,
        "bollinger_20_2": bb,
        "return_1d_pct": pct_return(close, 1),
        "return_5d_pct": pct_return(close, 5),
        "return_20d_pct": pct_return(close, 20),
    }

    required = {
        "previous_rth_close": prev.get("previous_rth_close"),
        "previous_rth_high": prev.get("previous_rth_high"),
        "previous_rth_low": prev.get("previous_rth_low"),
        "premarket_open": pm["open"],
        "premarket_high": pm["high"],
        "premarket_low": pm["low"],
        "premarket_close": pm["close"],
        "atr14": atr,
    }
    missing = classify_missing(required)
    missing["history_readiness"] = {
        "state": warmup["state"],
        "required_prior_rth_sessions": warmup["required_prior_rth_sessions"],
        "observed_prior_rth_sessions": warmup["observed_prior_rth_sessions"],
    }

    lineage = {
        "market_cache_version": MARKET_CACHE_VERSION,
        "warmup_contract_version": WARMUP_CONTRACT_VERSION,
        "required_warmup_rth_sessions": REQUIRED_WARMUP_RTH_SESSIONS,
        "source_files": [
            {"path": str(p), "sha256": sha256_file(p)}
            for p in source_paths
        ],
    }

    return raw, missing, lineage


def candidate_state(raw: dict, missing: dict) -> tuple[str, Optional[str], dict]:
    warmup = raw.get("history_readiness", {})
    if not warmup.get("ready", False):
        return "INSUFFICIENT_DATA", "SOURCE_HISTORY_WARMUP_INSUFFICIENT", {
            "required_core_data": False,
            "source_history_ready": False,
            "warmup_contract_version": WARMUP_CONTRACT_VERSION,
            "required_prior_rth_sessions": REQUIRED_WARMUP_RTH_SESSIONS,
            "observed_prior_rth_sessions": warmup.get("observed_prior_rth_sessions"),
            "weights_applied": False,
        }

    if missing["required_core_missing_count"] > 0:
        return "INSUFFICIENT_DATA", "REQUIRED_CORE_MISSING", {
            "required_core_data": False,
            "source_history_ready": True,
            "weights_applied": False,
        }

    pm_bars = raw["premarket"]["bar_count"]
    if pm_bars <= 0:
        return "INSUFFICIENT_DATA", "PREMARKET_MISSING", {
            "required_core_data": False,
            "source_history_ready": True,
            "weights_applied": False,
        }

    return "ELIGIBLE", "RAW_FEATURES_READY", {
        "required_core_data": True,
        "source_history_ready": True,
        "weights_applied": False,
        "factor_weights_status": "UNASSIGNED_RESEARCH_HYPOTHESES",
    }


def snapshot_asof_utc(trade_date: date, cutoff: time) -> datetime:
    local_dt = datetime.combine(trade_date, cutoff, tzinfo=CENTRAL_TZ)
    return local_dt.astimezone(UTC_TZ)


def generate_snapshot(
    store: PartitionStore,
    trade_date: date,
    snapshot_code: str,
    symbols: list[str],
) -> tuple[pd.DataFrame, dict]:
    cutoff = SNAPSHOT_TIMES[snapshot_code]
    asof = snapshot_asof_utc(trade_date, cutoff)

    mkt_ctx, mkt_missing = market_context(store, trade_date, cutoff)

    records: list[SnapshotCandidate] = []
    symbol_summary = []

    for idx, symbol in enumerate(symbols, start=1):
        print(f"[{idx}/{len(symbols)}] {symbol} {trade_date} {snapshot_code}")

        try:
            raw, missing, lineage = build_symbol_features(
                store, symbol, trade_date, cutoff
            )
            benchmark = point_in_time_sector_benchmark(symbol, trade_date)
            sec_ctx, sec_state = sector_context(
                store, benchmark, trade_date, cutoff
            )

            eligibility, gate_state, gates = candidate_state(raw, missing)

            context = {
                "market": mkt_ctx,
                "market_missing_states": mkt_missing,
                "sector": sec_ctx,
                "sector_state": sec_state,
                "sector_mapping_version": SECTOR_MAPPING_VERSION,
            }

            explanation = {
                "status": (
                    "Raw point-in-time features generated. No composite score "
                    "or research weights are applied in PMS-3."
                ),
                "sector_benchmark": benchmark,
            }

            for strategy in STRATEGY_FAMILIES:
                for direction in DIRECTIONS:
                    records.append(SnapshotCandidate(
                        trade_date=trade_date.isoformat(),
                        snapshot_code=snapshot_code,
                        snapshot_asof_utc=asof.isoformat(),
                        symbol=symbol,
                        strategy_family=strategy,
                        direction=direction,
                        eligibility_state=eligibility,
                        gate_state=gate_state,
                        composite_score=None,
                        raw_features_json=json.dumps(raw, separators=(",", ":"), default=str),
                        context_states_json=json.dumps(context, separators=(",", ":"), default=str),
                        gate_results_json=json.dumps(gates, separators=(",", ":"), default=str),
                        missing_data_json=json.dumps(missing, separators=(",", ":"), default=str),
                        explanation_json=json.dumps(explanation, separators=(",", ":"), default=str),
                        lineage_json=json.dumps(lineage, separators=(",", ":"), default=str),
                    ))

            symbol_summary.append({
                "symbol": symbol,
                "eligibility_state": eligibility,
                "gate_state": gate_state,
                "pm_bar_count": raw["premarket"]["bar_count"],
                "pm_exact_cutoff_bar_present": raw["premarket"]["exact_cutoff_bar_present"],
                "pm_staleness_minutes_at_cutoff": raw["premarket"]["staleness_minutes_at_cutoff"],
                "pm_observed_minute_density_pct": raw["premarket"]["observed_pm_minute_density_pct"],
                "sector_benchmark": benchmark,
                "sector_context_state": sec_state,
                "missing_required": missing["required_core_missing_count"],
                "history_readiness_state": raw["history_readiness"]["state"],
                "prior_rth_sessions_observed": raw["history_readiness"]["observed_prior_rth_sessions"],
            })

        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            print(f"  ERROR: {error_text}")

            missing = {
                "required_core_missing_count": 1,
                "items": [{"feature": "symbol_partition", "state": "INVALID"}],
                "error": error_text,
            }

            for strategy in STRATEGY_FAMILIES:
                for direction in DIRECTIONS:
                    records.append(SnapshotCandidate(
                        trade_date=trade_date.isoformat(),
                        snapshot_code=snapshot_code,
                        snapshot_asof_utc=asof.isoformat(),
                        symbol=symbol,
                        strategy_family=strategy,
                        direction=direction,
                        eligibility_state="INSUFFICIENT_DATA",
                        gate_state="SYMBOL_PROCESSING_ERROR",
                        composite_score=None,
                        raw_features_json="{}",
                        context_states_json=json.dumps({
                            "market": mkt_ctx,
                            "market_missing_states": mkt_missing,
                        }, separators=(",", ":"), default=str),
                        gate_results_json=json.dumps({
                            "required_core_data": False,
                            "weights_applied": False,
                        }, separators=(",", ":")),
                        missing_data_json=json.dumps(missing, separators=(",", ":")),
                        explanation_json=json.dumps({
                            "status": "Symbol snapshot generation failed."
                        }, separators=(",", ":")),
                        lineage_json="{}",
                    ))

            symbol_summary.append({
                "symbol": symbol,
                "eligibility_state": "INSUFFICIENT_DATA",
                "gate_state": "SYMBOL_PROCESSING_ERROR",
                "pm_bar_count": None,
                "sector_benchmark": point_in_time_sector_benchmark(symbol, trade_date),
                "sector_context_state": "INVALID",
                "missing_required": 1,
            })

    return pd.DataFrame([asdict(r) for r in records]), {
        "trade_date": trade_date.isoformat(),
        "snapshot_code": snapshot_code,
        "snapshot_asof_utc": asof.isoformat(),
        "candidate_universe_code": UNIVERSE_CODE,
        "candidate_universe_version": UNIVERSE_VERSION,
        "factor_registry_version": FACTOR_REGISTRY_VERSION,
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "snapshot_contract_version": SNAPSHOT_CONTRACT_VERSION,
        "sector_mapping_version": SECTOR_MAPPING_VERSION,
        "row_count": len(records),
        "symbol_count": len(symbols),
        "strategy_family_count": len(STRATEGY_FAMILIES),
        "direction_count": len(DIRECTIONS),
        "factor_weights_status": "UNASSIGNED_RESEARCH_HYPOTHESES",
        "warmup_contract_version": WARMUP_CONTRACT_VERSION,
        "required_warmup_rth_sessions": REQUIRED_WARMUP_RTH_SESSIONS,
        "symbol_summary": symbol_summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate PMS-3 historical SCAN_A/SCAN_B raw snapshot candidates."
    )
    parser.add_argument(
        "--trade-date",
        required=True,
        help="Historical trade date YYYY-MM-DD.",
    )
    parser.add_argument(
        "--snapshot-code",
        choices=["SCAN_A", "SCAN_B", "BOTH"],
        default="BOTH",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Optional symbol subset. Default: frozen PMPD_112_V1 universe.",
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    trade_date = date.fromisoformat(args.trade_date)
    symbols = [s.upper().strip() for s in (args.symbols or PMPD_112_V1)]

    root = repo_root()
    cache_root = (
        args.cache_root
        if args.cache_root is not None
        else root / "market_cache" / MARKET_CACHE_VERSION
    )
    output_root = (
        args.output_root
        if args.output_root is not None
        else root / "research_outputs" / "pms_snapshots"
    )
    output_root.mkdir(parents=True, exist_ok=True)

    store = PartitionStore(cache_root)

    snapshot_codes = (
        ["SCAN_A", "SCAN_B"]
        if args.snapshot_code == "BOTH"
        else [args.snapshot_code]
    )

    overall = []

    for snapshot_code in snapshot_codes:
        print()
        print(f"=== GENERATING {trade_date} {snapshot_code} ===")

        candidates, run_meta = generate_snapshot(
            store=store,
            trade_date=trade_date,
            snapshot_code=snapshot_code,
            symbols=symbols,
        )

        stem = f"{trade_date.isoformat()}_{snapshot_code.lower()}"
        csv_path = output_root / f"{stem}_candidates.csv"
        meta_path = output_root / f"{stem}_run.json"

        candidates.to_csv(csv_path, index=False)
        meta_path.write_text(
            json.dumps(run_meta, indent=2, default=str),
            encoding="utf-8",
        )

        eligibility_counts = (
            candidates[["symbol", "eligibility_state"]]
            .drop_duplicates()
            ["eligibility_state"]
            .value_counts()
            .to_dict()
        )

        summary = {
            "trade_date": trade_date.isoformat(),
            "snapshot_code": snapshot_code,
            "candidate_rows": len(candidates),
            "unique_symbols": candidates["symbol"].nunique(),
            "eligibility_counts_by_symbol": eligibility_counts,
            "csv": str(csv_path),
            "run_json": str(meta_path),
        }
        overall.append(summary)

        print()
        print("=== SNAPSHOT SUMMARY ===")
        print(json.dumps(summary, indent=2))

    print()
    print("=== PMS-3 GENERATION COMPLETE ===")
    print(json.dumps(overall, indent=2))


if __name__ == "__main__":
    main()
