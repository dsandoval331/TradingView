from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 9142026
REPS = 10000
RVOL_THRESHOLD = 1.5
SAFE_OPEN_5M = 9 * 60 + 35
SAFE_OPEN_15M = 9 * 60 + 45


def _outcome(s: pd.Series) -> pd.Series:
    return s.astype(str).str.upper().str.strip().replace({"BOTH": "AMBIGUOUS_SAME_BAR", "NEITHER": "UNRESOLVED"})


def _stats(df: pd.DataFrame) -> dict:
    o = _outcome(df["outcome"])
    fav = int((o == "FAVORABLE_FIRST").sum())
    adv = int((o == "ADVERSE_FIRST").sum())
    resolved = fav + adv
    return {
        "events": int(len(df)),
        "resolved": resolved,
        "favorable_first": fav,
        "adverse_first": adv,
        "rate": float(fav / resolved) if resolved else np.nan,
    }


def _cluster_boot_lift(df: pd.DataFrame, mask: pd.Series, base_mask: pd.Series) -> tuple[float, float, float]:
    syms = np.array(sorted(df["symbol"].astype(str).unique()))
    x = df[["symbol", "outcome"]].copy()
    x["outcome"] = _outcome(x["outcome"])
    x["fav"] = (x["outcome"] == "FAVORABLE_FIRST").astype(np.int64)
    x["adv"] = (x["outcome"] == "ADVERSE_FIRST").astype(np.int64)

    def counts(m: pd.Series) -> np.ndarray:
        return (
            x.loc[m.fillna(False)]
            .groupby("symbol")[["fav", "adv"]]
            .sum()
            .reindex(syms, fill_value=0)
            .to_numpy(dtype=np.int64)
        )

    sel = counts(mask)
    base = counts(base_mask)
    rng = np.random.default_rng(SEED)
    vals = np.empty(REPS, dtype=float)
    n = 0
    for _ in range(REPS):
        idx = rng.integers(0, len(syms), size=len(syms))
        sf, sa = sel[idx].sum(axis=0)
        bf, ba = base[idx].sum(axis=0)
        if sf + sa and bf + ba:
            vals[n] = sf / (sf + sa) - bf / (bf + ba)
            n += 1
    if not n:
        return (np.nan, np.nan, np.nan)
    return tuple(map(float, np.quantile(vals[:n], [0.025, 0.5, 0.975])))


def _test(df: pd.DataFrame, mask: pd.Series, base_mask: pd.Series, name: str) -> dict:
    st = _stats(df.loc[mask.fillna(False)])
    base = _stats(df.loc[base_mask.fillna(False)])
    lo, med, hi = _cluster_boot_lift(df, mask, base_mask)
    return {
        "test": name,
        **st,
        "base_resolved": base["resolved"],
        "base_rate": base["rate"],
        "lift": float(st["rate"] - base["rate"]) if np.isfinite(st["rate"]) and np.isfinite(base["rate"]) else np.nan,
        "ci95_lower": lo,
        "bootstrap_median": med,
        "ci95_upper": hi,
        "classification": "SUPPORTIVE" if np.isfinite(lo) and lo > 0 else ("NEGATIVE" if np.isfinite(hi) and hi < 0 else "CONDITIONAL"),
    }


def _load_cache(cache: Path, sym: str) -> pd.DataFrame | None:
    p = cache / sym / f"{sym}_2026.parquet"
    if not p.exists():
        return None
    d = pd.read_parquet(p).copy()
    d["timestamp_utc"] = pd.to_datetime(d["timestamp_utc"], utc=True)
    d["timestamp_et"] = d["timestamp_utc"].dt.tz_convert("America/New_York")
    d["trade_date"] = d["timestamp_et"].dt.date
    return d


def _daily_features(d: pd.DataFrame, volume_col: str, open_col: str, close_col: str) -> tuple[dict, dict]:
    r = d[(d["timestamp_et"].dt.time >= pd.Timestamp("09:30").time()) & (d["timestamp_et"].dt.time <= pd.Timestamp("15:59").time())].copy()
    if r.empty:
        return {}, {}
    r["bar5"] = r["timestamp_et"].dt.floor("5min")
    bars = r.groupby(["trade_date", "bar5"], as_index=False).agg(vol=(volume_col, "sum"), open=(open_col, "first"), close=(close_col, "last"))
    bars["clock"] = bars["bar5"].dt.strftime("%H:%M")
    dates = sorted(bars["trade_date"].unique())
    date_pos = {dt: i for i, dt in enumerate(dates)}
    by_clock = {clock: g.set_index("trade_date")["vol"] for clock, g in bars.groupby("clock")}

    rvol = {}
    opening = {}
    for row in bars.itertuples():
        pos = date_pos[row.trade_date]
        hist = dates[max(0, pos - 14):pos]
        h = by_clock[row.clock].reindex(hist).dropna()
        denom = float(h.mean()) if len(h) >= 5 else np.nan
        rvol[(row.trade_date, row.clock)] = float(row.vol) / denom if np.isfinite(denom) and denom > 0 else np.nan

    for dt, g in bars.groupby("trade_date"):
        g = g.sort_values("bar5")
        g930 = g[g["clock"] == "09:30"]
        g935 = g[g["clock"] == "09:35"]
        g940 = g[g["clock"] == "09:40"]
        if len(g930):
            o = float(g930.iloc[0]["open"])
            c5 = float(g930.iloc[0]["close"])
            c15 = float(g940.iloc[0]["close"]) if len(g940) else np.nan
            opening[dt] = {
                "open5_ret": c5 / o - 1.0 if o else np.nan,
                "open15_ret": c15 / o - 1.0 if o and np.isfinite(c15) else np.nan,
            }
    return rvol, opening


def run(root: Path) -> dict:
    inp = root / "research_outputs" / "pmpd" / "post9n_batch1" / "context_enriched.parquet"
    cache = root / "data" / "second1m_alt_entry_cache_v1" / "partitions"
    if not inp.exists():
        raise FileNotFoundError(inp)
    if not cache.exists():
        raise FileNotFoundError(cache)

    out = root / "research_outputs" / "pmpd" / "edge" / "e1_batch5"
    out.mkdir(parents=True, exist_ok=True)

    v = pd.read_parquet(inp).copy()
    v["outcome"] = _outcome(v["outcome"])
    v["trade_date"] = pd.to_datetime(v["trade_date"]).dt.date
    ts = pd.to_datetime(v["timestamp_et"])
    if getattr(ts.dt, "tz", None) is None:
        v["timestamp_et"] = ts.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
    else:
        v["timestamp_et"] = ts.dt.tz_convert("America/New_York")
    v["event_minute"] = v["timestamp_et"].dt.hour * 60 + v["timestamp_et"].dt.minute
    v["month"] = pd.to_datetime(v["trade_date"]).dt.to_period("M").astype(str)

    required = {"symbol", "direction", "gap_aligned", "opening_rvol14_mean_5m", "outcome", "event_minute"}
    missing = sorted(required - set(v.columns))
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    sample = next(iter(cache.glob("*/*_2026.parquet")), None)
    if sample is None:
        raise FileNotFoundError("No 2026 cache partitions found")
    cols = pd.read_parquet(sample).columns
    volume_col = next((c for c in ["volume", "v", "Volume"] if c in cols), None)
    open_col = next((c for c in ["open", "o", "Open"] if c in cols), None)
    close_col = next((c for c in ["close", "c", "Close"] if c in cols), None)
    if not all([volume_col, open_col, close_col]):
        raise KeyError("Required OHLCV columns not found in cache")

    v["signalbar_rvol14_mean_5m"] = np.nan
    v["opening_5m_ret"] = np.nan
    v["opening_15m_ret"] = np.nan

    total = v["symbol"].nunique()
    for n, sym in enumerate(sorted(v["symbol"].astype(str).unique()), 1):
        print(f"[{n}/{total}] BREAKOUT_VOLUME_MOMENTUM {sym}")
        d = _load_cache(cache, sym)
        if d is None:
            print(f"  MISSING_CACHE {sym}")
            continue
        rvol_map, opening_map = _daily_features(d, volume_col, open_col, close_col)
        idx = v["symbol"].astype(str).eq(sym)
        event_bar_start = v.loc[idx, "timestamp_et"].dt.floor("5min") - pd.Timedelta(minutes=5)
        dates = v.loc[idx, "trade_date"]
        clocks = event_bar_start.dt.strftime("%H:%M")
        v.loc[idx, "signalbar_rvol14_mean_5m"] = [rvol_map.get((dt, cl), np.nan) for dt, cl in zip(dates, clocks)]
        v.loc[idx, "opening_5m_ret"] = [opening_map.get(dt, {}).get("open5_ret", np.nan) for dt in dates]
        v.loc[idx, "opening_15m_ret"] = [opening_map.get(dt, {}).get("open15_ret", np.nan) for dt in dates]

    direction_sign = np.where(v["direction"].astype(str).str.upper().eq("BULL"), 1.0, -1.0)
    v["opening_5m_aligned"] = (v["opening_5m_ret"] * direction_sign) > 0
    v["opening_15m_aligned"] = (v["opening_15m_ret"] * direction_sign) > 0

    safe5 = (v["event_minute"] >= SAFE_OPEN_5M) & v["opening_5m_ret"].notna()
    safe15 = (v["event_minute"] >= SAFE_OPEN_15M) & v["opening_15m_ret"].notna()
    sig_rvol_avail = safe5 & v["signalbar_rvol14_mean_5m"].notna()
    opening_rvol_avail = safe5 & v["opening_rvol14_mean_5m"].notna()

    gap = v["gap_aligned"].fillna(False).astype(bool)
    high_open_rvol = v["opening_rvol14_mean_5m"] >= RVOL_THRESHOLD
    high_signal_rvol = v["signalbar_rvol14_mean_5m"] >= RVOL_THRESHOLD
    m5 = v["opening_5m_aligned"].fillna(False)
    m15 = v["opening_15m_aligned"].fillna(False)

    tests = [
        _test(v, safe5 & m5, safe5, "opening_5m_direction_aligned"),
        _test(v, safe15 & m15, safe15, "opening_15m_direction_aligned"),
        _test(v, sig_rvol_avail & high_signal_rvol, sig_rvol_avail, "signalbar_rvol14_mean>=1.5"),
        _test(v, sig_rvol_avail & high_signal_rvol & m5, sig_rvol_avail, "signalbar_rvol>=1.5 + opening_5m_aligned"),
        _test(v, opening_rvol_avail & high_open_rvol & m5, opening_rvol_avail, "opening_rvol>=1.5 + opening_5m_aligned"),
        _test(v, opening_rvol_avail & gap & high_open_rvol & m5, opening_rvol_avail, "gap_aligned + opening_rvol>=1.5 + opening_5m_aligned"),
        _test(v, sig_rvol_avail & gap & high_signal_rvol & m5, sig_rvol_avail, "gap_aligned + signalbar_rvol>=1.5 + opening_5m_aligned"),
    ]
    tests_df = pd.DataFrame(tests)
    tests_df.to_csv(out / "factor_combo_tests.csv", index=False)

    # Direction and monthly robustness for the two most policy-relevant combos.
    combo_defs = {
        "open_rvol_plus_open5": opening_rvol_avail & high_open_rvol & m5,
        "signalbar_rvol_plus_open5": sig_rvol_avail & high_signal_rvol & m5,
    }
    robust_rows = []
    for combo_name, sel in combo_defs.items():
        base = opening_rvol_avail if combo_name.startswith("open_") else sig_rvol_avail
        for direction in ["BULL", "BEAR"]:
            dm = v["direction"].astype(str).str.upper().eq(direction)
            st = _test(v, sel & dm, base & dm, f"{combo_name}_{direction}")
            robust_rows.append({"dimension": "direction", "value": direction, "combo": combo_name, **st})
        for month in sorted(v["month"].dropna().unique()):
            mm = v["month"].eq(month)
            st = _test(v, sel & mm, base & mm, f"{combo_name}_{month}")
            robust_rows.append({"dimension": "month", "value": month, "combo": combo_name, **st})
    robust = pd.DataFrame(robust_rows)
    robust.to_csv(out / "robustness.csv", index=False)

    # Correlation-style overlap table to show whether momentum is merely tagging the same events as RVOL.
    overlap = pd.DataFrame({
        "opening_rvol_high": high_open_rvol & opening_rvol_avail,
        "signalbar_rvol_high": high_signal_rvol & sig_rvol_avail,
        "opening_5m_aligned": m5 & safe5,
        "gap_aligned": gap,
    }).astype(int).corr()
    overlap.to_csv(out / "feature_overlap_correlation.csv")

    def _pick(name: str) -> dict:
        return next(t for t in tests if t["test"] == name)

    primary = _pick("opening_rvol>=1.5 + opening_5m_aligned")
    signal_combo = _pick("signalbar_rvol>=1.5 + opening_5m_aligned")
    mom5 = _pick("opening_5m_direction_aligned")

    valid_primary_months = robust[(robust["combo"] == "open_rvol_plus_open5") & (robust["dimension"] == "month") & robust["lift"].notna()]
    valid_primary_dirs = robust[(robust["combo"] == "open_rvol_plus_open5") & (robust["dimension"] == "direction") & robust["lift"].notna()]

    summary = {
        "step": "PMPD-EDGE-E1-B5",
        "purpose": "Independent contextual-family test of breakout-volume anomaly and opening momentum, while carrying the frozen opening-RVOL >=1.5 feature without retuning.",
        "frozen_rvol_threshold": RVOL_THRESHOLD,
        "availability": {
            "opening_5m_momentum": "usable only at/after 09:35 ET",
            "opening_15m_momentum": "usable only at/after 09:45 ET",
            "signalbar_rvol": "uses the immediately completed 5m bar ending at the event timestamp",
        },
        "opening_5m_momentum": mom5,
        "primary_combo_opening_rvol_plus_open5": primary,
        "signalbar_rvol_plus_open5": signal_combo,
        "robustness_primary_combo": {
            "months_positive_lift": int((valid_primary_months["lift"] > 0).sum()),
            "months_tested": int(len(valid_primary_months)),
            "directions_positive_lift": int((valid_primary_dirs["lift"] > 0).sum()),
            "directions_tested": int(len(valid_primary_dirs)),
        },
        "governance": {
            "research_only": True,
            "2026_is_development_evidence": True,
            "v5_modified": False,
            "rvol_threshold_retuned": False,
            "production_rule_authorized": False,
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print("OUTPUT_DIR=", out)
    print("OPEN5_ALIGNMENT_RATE=", mom5["rate"])
    print("OPEN5_ALIGNMENT_LIFT=", mom5["lift"])
    print("OPEN5_ALIGNMENT_CI=", [mom5["ci95_lower"], mom5["ci95_upper"]])
    print("PRIMARY_OPEN_RVOL_PLUS_OPEN5_RATE=", primary["rate"])
    print("PRIMARY_OPEN_RVOL_PLUS_OPEN5_LIFT=", primary["lift"])
    print("PRIMARY_OPEN_RVOL_PLUS_OPEN5_CI=", [primary["ci95_lower"], primary["ci95_upper"]])
    print("SIGNALBAR_RVOL_PLUS_OPEN5_RATE=", signal_combo["rate"])
    print("SIGNALBAR_RVOL_PLUS_OPEN5_LIFT=", signal_combo["lift"])
    print("SIGNALBAR_RVOL_PLUS_OPEN5_CI=", [signal_combo["ci95_lower"], signal_combo["ci95_upper"]])
    print("PRIMARY_MONTHS_POSITIVE_LIFT=", summary["robustness_primary_combo"]["months_positive_lift"], "/", summary["robustness_primary_combo"]["months_tested"])
    print("PRIMARY_DIRECTIONS_POSITIVE_LIFT=", summary["robustness_primary_combo"]["directions_positive_lift"], "/", summary["robustness_primary_combo"]["directions_tested"])

    return {
        "output_dir": str(out),
        "summary": str(out / "summary.json"),
        "tests": str(out / "factor_combo_tests.csv"),
        "robustness": str(out / "robustness.csv"),
        "overlap": str(out / "feature_overlap_correlation.csv"),
    }
