from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 9122026
REPS = 10000
RVOL_THRESHOLD = 1.5
SAFE_OPEN_MINUTE = 9 * 60 + 35


def _outcome(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
        .str.upper()
        .str.strip()
        .replace({"BOTH": "AMBIGUOUS_SAME_BAR", "NEITHER": "UNRESOLVED"})
    )


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
    if not len(syms):
        return (np.nan, np.nan, np.nan)

    x = df[["symbol", "outcome"]].copy()
    x["outcome"] = _outcome(x["outcome"])
    x["fav"] = (x["outcome"] == "FAVORABLE_FIRST").astype(np.int64)
    x["adv"] = (x["outcome"] == "ADVERSE_FIRST").astype(np.int64)

    def counts_for(m: pd.Series) -> np.ndarray:
        g = x.loc[m.fillna(False), ["symbol", "fav", "adv"]]
        return (
            g.groupby("symbol")[["fav", "adv"]]
            .sum()
            .reindex(syms, fill_value=0)
            .to_numpy(dtype=np.int64)
        )

    sel = counts_for(mask)
    base = counts_for(base_mask)
    rng = np.random.default_rng(SEED)
    vals = np.empty(REPS, dtype=float)
    n_valid = 0
    n_syms = len(syms)

    for _ in range(REPS):
        idx = rng.integers(0, n_syms, size=n_syms)
        sf, sa = sel[idx].sum(axis=0)
        bf, ba = base[idx].sum(axis=0)
        if sf + sa and bf + ba:
            vals[n_valid] = sf / (sf + sa) - bf / (bf + ba)
            n_valid += 1

    if not n_valid:
        return (np.nan, np.nan, np.nan)
    return tuple(map(float, np.quantile(vals[:n_valid], [0.025, 0.5, 0.975])))


def _test(df: pd.DataFrame, mask: pd.Series, base_mask: pd.Series, name: str) -> dict:
    st = _stats(df.loc[mask.fillna(False)])
    base = _stats(df.loc[base_mask.fillna(False)])
    lo, med, hi = _cluster_boot_lift(df, mask, base_mask)
    return {
        "test": name,
        **st,
        "base_resolved": base["resolved"],
        "base_rate": base["rate"],
        "lift_vs_base": float(st["rate"] - base["rate"]) if np.isfinite(st["rate"]) and np.isfinite(base["rate"]) else np.nan,
        "lift_ci95_lower": lo,
        "lift_bootstrap_median": med,
        "lift_ci95_upper": hi,
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


def _build_prior_completed_rvol14(cache_df: pd.DataFrame, volume_col: str) -> dict:
    r = cache_df[
        (cache_df["timestamp_et"].dt.time >= pd.Timestamp("09:30").time())
        & (cache_df["timestamp_et"].dt.time <= pd.Timestamp("15:59").time())
    ].copy()
    if r.empty:
        return {}

    r["bar5"] = r["timestamp_et"].dt.floor("5min")
    bars = r.groupby(["trade_date", "bar5"], as_index=False).agg(vol=(volume_col, "sum"))
    bars["clock"] = bars["bar5"].dt.strftime("%H:%M")
    dates = sorted(bars["trade_date"].unique())
    date_pos = {d: i for i, d in enumerate(dates)}
    by_clock = {clock: g.set_index("trade_date")["vol"] for clock, g in bars.groupby("clock")}

    rvol = {}
    for row in bars.itertuples():
        pos = date_pos[row.trade_date]
        hist = dates[max(0, pos - 14):pos]
        series = by_clock[row.clock]
        h = series.reindex(hist).dropna()
        mean14 = float(h.mean()) if len(h) >= 5 else np.nan
        rvol[(row.trade_date, row.clock)] = float(row.vol) / mean14 if np.isfinite(mean14) and mean14 > 0 else np.nan
    return rvol


def run(root: Path) -> dict:
    inp = root / "research_outputs" / "pmpd" / "post9n_batch1" / "context_enriched.parquet"
    cache = root / "data" / "second1m_alt_entry_cache_v1" / "partitions"
    if not inp.exists():
        raise FileNotFoundError(inp)
    if not cache.exists():
        raise FileNotFoundError(cache)

    out = root / "research_outputs" / "pmpd" / "edge" / "e1_batch3"
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

    # Reconstruct a strictly signal-time-safe RVOL feature using ONLY the immediately prior completed 5m bar.
    sample = next(iter(cache.glob("*/*_2026.parquet")), None)
    if sample is None:
        raise FileNotFoundError("No 2026 cache partitions found")
    sample_cols = pd.read_parquet(sample).columns
    volume_col = next((c for c in ["volume", "v", "Volume"] if c in sample_cols), None)
    if volume_col is None:
        raise KeyError("No volume column found in cache")

    v["prior_completed_rvol14_mean_5m"] = np.nan
    total_syms = v["symbol"].nunique()
    symbols_enriched = 0
    for n, sym in enumerate(sorted(v["symbol"].astype(str).unique()), 1):
        print(f"[{n}/{total_syms}] PRIOR_COMPLETED_RVOL {sym}")
        d = _load_cache(cache, sym)
        if d is None:
            print(f"  MISSING_CACHE {sym}")
            continue
        rvol_map = _build_prior_completed_rvol14(d, volume_col)
        idx = v["symbol"].astype(str).eq(sym)
        starts = v.loc[idx, "timestamp_et"].dt.floor("5min") - pd.Timedelta(minutes=5)
        dates = v.loc[idx, "trade_date"]
        clocks = starts.dt.strftime("%H:%M")
        v.loc[idx, "prior_completed_rvol14_mean_5m"] = [rvol_map.get((date, clock), np.nan) for date, clock in zip(dates, clocks)]
        symbols_enriched += 1

    safe_mask = (v["event_minute"] >= SAFE_OPEN_MINUTE) & v["opening_rvol14_mean_5m"].notna()
    frozen_primary = safe_mask & v["gap_aligned"].fillna(False) & (v["opening_rvol14_mean_5m"] >= RVOL_THRESHOLD)

    prior_available = v["prior_completed_rvol14_mean_5m"].notna()
    prior_base = safe_mask & prior_available
    prior_rvol = prior_base & (v["prior_completed_rvol14_mean_5m"] >= RVOL_THRESHOLD)
    prior_gap_rvol = prior_rvol & v["gap_aligned"].fillna(False)

    tests = [
        _test(v, frozen_primary, safe_mask, "frozen gap_aligned + opening_rvol14_mean>=1.5"),
        _test(v, prior_rvol, prior_base, "prior_completed_rvol14_mean>=1.5"),
        _test(v, prior_gap_rvol, prior_base, "gap_aligned + prior_completed_rvol14_mean>=1.5"),
    ]
    tests_df = pd.DataFrame(tests)
    tests_df.to_csv(out / "incremental_tests.csv", index=False)

    # Direction decomposition for the frozen opening-RVOL hypothesis and prior-completed RVOL alternative.
    direction_rows = []
    for direction in ["BULL", "BEAR"]:
        dm = v["direction"].astype(str).str.upper().eq(direction)
        for label, sel, base in [
            ("frozen_opening", frozen_primary & dm, safe_mask & dm),
            ("prior_completed", prior_gap_rvol & dm, prior_base & dm),
        ]:
            st = _test(v, sel, base, f"{label}_{direction}")
            direction_rows.append({"direction": direction, "variant": label, **st})
    pd.DataFrame(direction_rows).to_csv(out / "direction_robustness.csv", index=False)

    # Timing decomposition. These bins are frozen for robustness description, not threshold selection.
    time_bins = [
        ("09:35-09:59", 575, 599),
        ("10:00-10:59", 600, 659),
        ("11:00-12:59", 660, 779),
        ("13:00-15:59", 780, 959),
    ]
    timing_rows = []
    for label, lo_min, hi_min in time_bins:
        tm = v["event_minute"].between(lo_min, hi_min)
        st = _test(v, frozen_primary & tm, safe_mask & tm, f"frozen_opening_{label}")
        timing_rows.append({"time_bucket": label, **st})
    timing = pd.DataFrame(timing_rows)
    timing.to_csv(out / "timing_robustness.csv", index=False)

    # Monthly decomposition of frozen opening-RVOL hypothesis.
    month_rows = []
    for month in sorted(v["month"].dropna().unique()):
        mm = v["month"].eq(month)
        st = _test(v, frozen_primary & mm, safe_mask & mm, f"month_{month}")
        month_rows.append({"month": month, **st})
    monthly = pd.DataFrame(month_rows)
    monthly.to_csv(out / "monthly_robustness.csv", index=False)

    # Concentration audit: event shares by symbol/date and leave-one-symbol-out lift range.
    selected = v.loc[frozen_primary].copy()
    sym_counts = selected.groupby("symbol").size().sort_values(ascending=False)
    date_counts = selected.groupby("trade_date").size().sort_values(ascending=False)
    total_selected = max(int(len(selected)), 1)

    concentration = {
        "selected_events": int(len(selected)),
        "top1_symbol_share": float(sym_counts.head(1).sum() / total_selected),
        "top5_symbol_share": float(sym_counts.head(5).sum() / total_selected),
        "top10_symbol_share": float(sym_counts.head(10).sum() / total_selected),
        "top1_date_share": float(date_counts.head(1).sum() / total_selected),
        "top5_date_share": float(date_counts.head(5).sum() / total_selected),
        "top10_date_share": float(date_counts.head(10).sum() / total_selected),
        "top_symbols": {str(k): int(val) for k, val in sym_counts.head(10).items()},
        "top_dates": {str(k): int(val) for k, val in date_counts.head(10).items()},
    }

    l1o_rows = []
    for sym in sorted(v["symbol"].astype(str).unique()):
        keep = ~v["symbol"].astype(str).eq(sym)
        sel_st = _stats(v.loc[frozen_primary & keep])
        base_st = _stats(v.loc[safe_mask & keep])
        lift = float(sel_st["rate"] - base_st["rate"]) if np.isfinite(sel_st["rate"]) and np.isfinite(base_st["rate"]) else np.nan
        l1o_rows.append({"left_out_symbol": sym, "selected_resolved": sel_st["resolved"], "selected_rate": sel_st["rate"], "base_rate": base_st["rate"], "lift": lift})
    l1o = pd.DataFrame(l1o_rows)
    l1o.to_csv(out / "leave_one_symbol_out.csv", index=False)

    # Stratified time+direction incremental check: does frozen RVOL selection tend to beat its local base strata?
    strata_rows = []
    for direction in ["BULL", "BEAR"]:
        dm = v["direction"].astype(str).str.upper().eq(direction)
        for label, lo_min, hi_min in time_bins:
            tm = v["event_minute"].between(lo_min, hi_min)
            base_st = _stats(v.loc[safe_mask & dm & tm])
            sel_st = _stats(v.loc[frozen_primary & dm & tm])
            strata_rows.append({
                "direction": direction,
                "time_bucket": label,
                "base_resolved": base_st["resolved"],
                "base_rate": base_st["rate"],
                "selected_resolved": sel_st["resolved"],
                "selected_rate": sel_st["rate"],
                "lift": float(sel_st["rate"] - base_st["rate"]) if np.isfinite(sel_st["rate"]) and np.isfinite(base_st["rate"]) else np.nan,
            })
    strata = pd.DataFrame(strata_rows)
    strata.to_csv(out / "time_direction_strata.csv", index=False)

    valid_strata = strata[strata["selected_resolved"] > 0].copy()
    weights = valid_strata["selected_resolved"].to_numpy(dtype=float)
    weighted_strata_lift = float(np.average(valid_strata["lift"], weights=weights)) if len(valid_strata) and weights.sum() > 0 else np.nan

    primary = tests[0]
    prior_combo = tests[2]
    summary = {
        "step": "PMPD-EDGE-E1-B3",
        "purpose": "Incremental-edge, concentration, timing, direction, and strictly prior-completed-bar RVOL audit.",
        "governance": {
            "research_only": True,
            "2026_is_development_evidence": True,
            "v5_modified": False,
            "rvol_threshold_retuned": False,
            "rvol_threshold": RVOL_THRESHOLD,
            "production_rule_authorized": False,
        },
        "signal_time_rules": {
            "opening_rvol": "09:30-09:34 volume is usable only at or after 09:35 ET.",
            "prior_completed_rvol": "Uses the immediately preceding fully completed 5m bar, never the event-containing 5m bar.",
        },
        "volume_column": volume_col,
        "symbols_enriched": symbols_enriched,
        "prior_completed_rvol_coverage_pct": float(v["prior_completed_rvol14_mean_5m"].notna().mean() * 100.0),
        "frozen_primary": primary,
        "prior_completed_gap_rvol": prior_combo,
        "concentration": concentration,
        "leave_one_symbol_out": {
            "tests": int(len(l1o)),
            "positive_lift": int((l1o["lift"] > 0).sum()),
            "min_lift": float(l1o["lift"].min()) if len(l1o) else np.nan,
            "median_lift": float(l1o["lift"].median()) if len(l1o) else np.nan,
            "max_lift": float(l1o["lift"].max()) if len(l1o) else np.nan,
        },
        "time_direction_strata": {
            "positive_lift_strata": int((valid_strata["lift"] > 0).sum()),
            "strata_tested": int(len(valid_strata)),
            "selected_resolved_weighted_lift": weighted_strata_lift,
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print("OUTPUT_DIR=", out)
    print("FROZEN_PRIMARY_RATE=", primary["rate"])
    print("FROZEN_PRIMARY_LIFT=", primary["lift_vs_base"])
    print("FROZEN_PRIMARY_LIFT_CI=", [primary["lift_ci95_lower"], primary["lift_ci95_upper"]])
    print("PRIOR_COMPLETED_GAP_RVOL_RATE=", prior_combo["rate"])
    print("PRIOR_COMPLETED_GAP_RVOL_LIFT=", prior_combo["lift_vs_base"])
    print("PRIOR_COMPLETED_GAP_RVOL_LIFT_CI=", [prior_combo["lift_ci95_lower"], prior_combo["lift_ci95_upper"]])
    print("TOP10_SYMBOL_SHARE=", concentration["top10_symbol_share"])
    print("L1O_POSITIVE_LIFT=", summary["leave_one_symbol_out"]["positive_lift"], "/", summary["leave_one_symbol_out"]["tests"])
    print("TIME_DIRECTION_POSITIVE_STRATA=", summary["time_direction_strata"]["positive_lift_strata"], "/", summary["time_direction_strata"]["strata_tested"])

    return {
        "output_dir": str(out),
        "summary": str(out / "summary.json"),
        "incremental_tests": str(out / "incremental_tests.csv"),
        "direction_robustness": str(out / "direction_robustness.csv"),
        "timing_robustness": str(out / "timing_robustness.csv"),
        "monthly_robustness": str(out / "monthly_robustness.csv"),
        "leave_one_symbol_out": str(out / "leave_one_symbol_out.csv"),
        "time_direction_strata": str(out / "time_direction_strata.csv"),
    }
