from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 9102026
REPS = 5000
START = pd.Timestamp("2026-01-05").date()
END = pd.Timestamp("2026-09-02").date()


def _outcome(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
        .str.upper()
        .str.strip()
        .replace({"BOTH": "AMBIGUOUS_SAME_BAR", "NEITHER": "UNRESOLVED"})
    )


def _stats(df: pd.DataFrame):
    o = _outcome(df.outcome)
    f = int((o == "FAVORABLE_FIRST").sum())
    a = int((o == "ADVERSE_FIRST").sum())
    r = f + a
    return f, a, r, (f / r if r else np.nan)


def _boot(df: pd.DataFrame, mask: pd.Series, base_rate: float, reps: int = REPS):
    """Paired symbol-cluster bootstrap using pre-aggregated symbol counts."""
    g = df.loc[mask.fillna(False), ["symbol", "outcome"]].copy()
    if g.empty:
        return (np.nan, np.nan, np.nan)

    g["outcome"] = _outcome(g.outcome)
    g["fav"] = (g.outcome == "FAVORABLE_FIRST").astype(np.int64)
    g["adv"] = (g.outcome == "ADVERSE_FIRST").astype(np.int64)

    syms = np.array(sorted(df.symbol.unique()))
    counts = (
        g.groupby("symbol")[["fav", "adv"]]
        .sum()
        .reindex(syms, fill_value=0)
        .to_numpy(dtype=np.int64)
    )

    rng = np.random.default_rng(SEED)
    vals = np.empty(reps, dtype=float)
    n_valid = 0
    n_syms = len(syms)

    for _ in range(reps):
        idx = rng.integers(0, n_syms, size=n_syms)
        sampled = counts[idx].sum(axis=0)
        f, a = int(sampled[0]), int(sampled[1])
        if f + a:
            vals[n_valid] = f / (f + a) - base_rate
            n_valid += 1

    if not n_valid:
        return (np.nan, np.nan, np.nan)
    return tuple(map(float, np.quantile(vals[:n_valid], [0.025, 0.5, 0.975])))


def _load_cache(cache: Path, sym: str) -> pd.DataFrame | None:
    p = cache / sym / f"{sym}_2026.parquet"
    if not p.exists():
        return None
    d = pd.read_parquet(p).copy()
    d["timestamp_utc"] = pd.to_datetime(d.timestamp_utc, utc=True)
    d["timestamp_et"] = d.timestamp_utc.dt.tz_convert("America/New_York")
    d["trade_date"] = d.timestamp_et.dt.date
    return d


def _benchmark_returns(events: pd.DataFrame, bench: pd.DataFrame) -> pd.Series:
    """Vectorized as-of benchmark return from 09:30 open to each event timestamp."""
    out = pd.Series(np.nan, index=events.index, dtype=float)
    rth_start = pd.Timestamp("09:30").time()
    rth_end = pd.Timestamp("15:59").time()

    for date, idx in events.groupby("trade_date").groups.items():
        b = bench[
            (bench.trade_date == date)
            & (bench.timestamp_et.dt.time >= rth_start)
            & (bench.timestamp_et.dt.time <= rth_end)
        ].sort_values("timestamp_et")
        if b.empty:
            continue

        first_open = float(b.iloc[0].open)
        b = b[["timestamp_et", "close"]].copy()
        b["bench_ret"] = b.close.astype(float) / first_open - 1.0

        e = events.loc[idx, ["timestamp_et"]].sort_values("timestamp_et").copy()
        e["_idx"] = e.index
        merged = pd.merge_asof(e, b[["timestamp_et", "bench_ret"]], on="timestamp_et", direction="backward")
        out.loc[merged._idx.to_numpy()] = merged.bench_ret.to_numpy()

    return out


def _build_rvol_maps(
    bars: pd.DataFrame,
    primary_sessions: int = 14,
    sensitivity_sessions: int = 20,
):
    """
    Build fixed-before-results RVOL maps.

    Primary literature-aligned definition:
      current 5m volume / mean volume for same clock bar over previous 14 sessions.

    Sensitivity definition retained from the earlier draft:
      current 5m volume / median volume for same clock bar over previous 20 sessions.
    """
    dates = sorted(bars.trade_date.unique())
    by_clock = {clock: g.set_index("trade_date").vol for clock, g in bars.groupby("clock")}
    rvol14 = {}
    rvol20med = {}

    date_pos = {d: i for i, d in enumerate(dates)}
    for row in bars.itertuples():
        pos = date_pos[row.trade_date]
        hist14 = dates[max(0, pos - primary_sessions):pos]
        hist20 = dates[max(0, pos - sensitivity_sessions):pos]
        series = by_clock[row.clock]

        h14 = series.reindex(hist14).dropna()
        h20 = series.reindex(hist20).dropna()

        mean14 = float(h14.mean()) if len(h14) >= 5 else np.nan
        med20 = float(h20.median()) if len(h20) >= 5 else np.nan

        rvol14[(row.trade_date, row.clock)] = float(row.vol) / mean14 if np.isfinite(mean14) and mean14 > 0 else np.nan
        rvol20med[(row.trade_date, row.clock)] = float(row.vol) / med20 if np.isfinite(med20) and med20 > 0 else np.nan

    return rvol14, rvol20med


def run(root: Path) -> dict:
    v5p = root / "research_outputs" / "pmpd" / "9m" / "pmpd_v5_9m_oos_candidate_dp4_v1.parquet"
    cache = root / "data" / "second1m_alt_entry_cache_v1" / "partitions"

    if not v5p.exists():
        raise FileNotFoundError(v5p)
    if not cache.exists():
        raise FileNotFoundError(cache)

    out = root / "research_outputs" / "pmpd" / "post9n_batch1"
    out.mkdir(parents=True, exist_ok=True)

    v = pd.read_parquet(v5p).copy()
    v["trade_date"] = pd.to_datetime(v.trade_date).dt.date
    v = v[v.trade_date.between(START, END)].copy()
    v["outcome"] = _outcome(v.outcome)
    v["timestamp_utc"] = pd.to_datetime(v.timestamp_utc, utc=True)
    v["timestamp_et"] = v.timestamp_utc.dt.tz_convert("America/New_York")

    v["gap_aligned"] = np.where(
        v.direction.str.upper().eq("BULL"),
        v.overnight_gap_pct > 0,
        v.overnight_gap_pct < 0,
    )
    v["gap_abs"] = v.overnight_gap_pct.abs()
    v["event_minute"] = v.timestamp_et.dt.hour * 60 + v.timestamp_et.dt.minute
    v["time_bucket"] = pd.cut(
        v.event_minute,
        [569, 629, 689, 749, 809, 869, 929, 989, 2000],
        labels=[
            "09:30-10:29", "10:30-11:29", "11:30-12:29", "12:30-13:29",
            "13:30-14:29", "14:30-15:29", "15:30-16:29", "16:30+",
        ],
    )

    for c in ["gap_abs", "six_level_scale_ratio", "stack_width_pct_geometry"]:
        if c in v.columns:
            v[c + "_quartile"] = pd.qcut(v[c], 4, duplicates="drop")

    _, _, base_res, base_rate = _stats(v)

    # Market context enrichment.
    bench = {s: _load_cache(cache, s) for s in ["SPY", "QQQ"]}
    bench = {k: d for k, d in bench.items() if d is not None}
    sign = np.where(v.direction.str.upper().eq("BULL"), 1, -1)

    for sym, d in bench.items():
        col = sym.lower() + "_ret_to_event"
        v[col] = _benchmark_returns(v, d)
        v[sym.lower() + "_aligned"] = (v[col] * sign) > 0

    if {"spy_aligned", "qqq_aligned"}.issubset(v.columns):
        v["market_both_aligned"] = v.spy_aligned & v.qqq_aligned

    # RVOL enrichment: 14-session mean is primary; 20-session median is sensitivity.
    rvol_cols = [
        "opening_rvol14_mean_5m", "eventbar_rvol14_mean_5m",
        "opening_rvol20_median_5m", "eventbar_rvol20_median_5m",
    ]
    for c in rvol_cols:
        v[c] = np.nan

    volume_col = None
    sample = next(iter(cache.glob("*/*_2026.parquet")), None)
    if sample is not None:
        cols = pd.read_parquet(sample).columns
        volume_col = next((c for c in ["volume", "v", "Volume"] if c in cols), None)

    symbols_with_cache = 0
    symbols_enriched = 0
    if volume_col:
        total_syms = v.symbol.nunique()
        for n, sym in enumerate(sorted(v.symbol.unique()), 1):
            print(f"[{n}/{total_syms}] CONTEXT {sym}")
            d = _load_cache(cache, sym)
            if d is None:
                print(f"  MISSING_CACHE {sym}")
                continue
            symbols_with_cache += 1

            r = d[
                (d.timestamp_et.dt.time >= pd.Timestamp("09:30").time())
                & (d.timestamp_et.dt.time <= pd.Timestamp("15:59").time())
            ].copy()
            if r.empty:
                print(f"  EMPTY_RTH {sym}")
                continue

            r["bar5"] = r.timestamp_et.dt.floor("5min")
            bars = r.groupby(["trade_date", "bar5"], as_index=False).agg(vol=(volume_col, "sum"))
            bars["clock"] = bars.bar5.dt.strftime("%H:%M")
            r14, r20 = _build_rvol_maps(bars)

            idx = v.symbol == sym
            dates = v.loc[idx, "trade_date"]
            clocks = v.loc[idx, "timestamp_et"].dt.floor("5min").dt.strftime("%H:%M")

            v.loc[idx, "opening_rvol14_mean_5m"] = [r14.get((date, "09:30"), np.nan) for date in dates]
            v.loc[idx, "eventbar_rvol14_mean_5m"] = [r14.get((date, clock), np.nan) for date, clock in zip(dates, clocks)]
            v.loc[idx, "opening_rvol20_median_5m"] = [r20.get((date, "09:30"), np.nan) for date in dates]
            v.loc[idx, "eventbar_rvol20_median_5m"] = [r20.get((date, clock), np.nan) for date, clock in zip(dates, clocks)]
            symbols_enriched += 1
    else:
        print("RVOL_ENRICHMENT_UNAVAILABLE: no volume column found in cache")

    rows = []

    def test(name, mask, family):
        mask = mask.fillna(False)
        g = v[mask]
        f, a, r, rate = _stats(g)
        if not r:
            return
        lo, med, hi = _boot(v, mask, base_rate)
        rows.append(
            dict(
                family=family,
                test=name,
                events=len(g),
                resolved=r,
                favorable_first=f,
                adverse_first=a,
                resolved_favorable_rate=rate,
                lift_vs_all=rate - base_rate,
                ci95_lower=lo,
                bootstrap_median=med,
                ci95_upper=hi,
            )
        )

    test("gap_aligned", v.gap_aligned, "gap")

    for c, fam in [
        ("gap_abs_quartile", "gap"),
        ("six_level_scale_ratio_quartile", "geometry"),
        ("stack_width_pct_geometry_quartile", "geometry"),
    ]:
        if c in v.columns:
            for q in v[c].dropna().unique():
                test(f"{c}_{q}", v[c] == q, fam)

    for q in v.time_bucket.dropna().unique():
        test(f"time_{q}", v.time_bucket == q, "time")

    for col, fam in [
        ("opening_rvol14_mean_5m", "rvol_primary"),
        ("eventbar_rvol14_mean_5m", "rvol_primary"),
        ("opening_rvol20_median_5m", "rvol_sensitivity"),
        ("eventbar_rvol20_median_5m", "rvol_sensitivity"),
    ]:
        if v[col].notna().any():
            for th in [1.0, 1.5, 2.0, 3.0]:
                test(f"{col}_ge_{th}", v[col] >= th, fam)

    for c in ["spy_aligned", "qqq_aligned", "market_both_aligned"]:
        if c in v.columns:
            test(c, v[c], "market")

    factors = pd.DataFrame(rows)
    if not factors.empty:
        factors = factors.sort_values(["ci95_lower", "lift_vs_all"], ascending=False)
    factors.to_csv(out / "factor_results.csv", index=False)

    combos = []

    def combo(name, mask):
        mask = mask.fillna(False)
        g = v[mask]
        f, a, r, rate = _stats(g)
        if r < 100:
            return
        lo, med, hi = _boot(v, mask, base_rate)
        combos.append(
            dict(
                combo=name,
                events=len(g),
                resolved=r,
                rate=rate,
                lift_vs_all=rate - base_rate,
                ci95_lower=lo,
                bootstrap_median=med,
                ci95_upper=hi,
            )
        )

    if v.opening_rvol14_mean_5m.notna().any():
        hi = v.opening_rvol14_mean_5m >= 1.5
        combo("gap_aligned + opening_rvol14_mean>=1.5", v.gap_aligned & hi)
        if "market_both_aligned" in v.columns:
            combo("gap + opening_rvol14_mean>=1.5 + market", v.gap_aligned & hi & v.market_both_aligned)
            combo("opening_rvol14_mean>=1.5 + market", hi & v.market_both_aligned)

    if v.eventbar_rvol14_mean_5m.notna().any():
        combo("gap_aligned + eventbar_rvol14_mean>=1.5", v.gap_aligned & (v.eventbar_rvol14_mean_5m >= 1.5))

    if "market_both_aligned" in v.columns:
        combo("gap_aligned + market", v.gap_aligned & v.market_both_aligned)

    cdf = pd.DataFrame(combos)
    if not cdf.empty:
        cdf = cdf.sort_values(["ci95_lower", "lift_vs_all"], ascending=False)
    cdf.to_csv(out / "combo_results.csv", index=False)
    v.to_parquet(out / "context_enriched.parquet", index=False)

    rvol_coverage = {
        c: {
            "non_null": int(v[c].notna().sum()),
            "coverage_pct": float(v[c].notna().mean() * 100.0),
        }
        for c in rvol_cols
    }

    summary = {
        "step": "PMPD-POST9N-B1",
        "baseline": {
            "events": len(v),
            "resolved": base_res,
            "resolved_favorable_rate": base_rate,
        },
        "v5_input": str(v5p),
        "volume_column": volume_col,
        "benchmarks": sorted(bench),
        "symbols_with_cache": symbols_with_cache,
        "symbols_enriched": symbols_enriched,
        "rvol_definition_primary": "same-clock 5m volume / mean of previous 14 sessions",
        "rvol_definition_sensitivity": "same-clock 5m volume / median of previous 20 sessions",
        "rvol_coverage": rvol_coverage,
        "factor_tests": len(factors),
        "combo_tests": len(cdf),
        "top_factors": factors.head(15).to_dict("records") if len(factors) else [],
        "top_combos": cdf.head(15).to_dict("records") if len(cdf) else [],
        "governance": {
            "v5_modified": False,
            "h2h_modified": False,
            "production_rule_authorized": False,
            "research_only": True,
            "2026_context_filter_work_is_development_evidence": True,
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print("OUTPUT_DIR=", out)
    print("BASELINE_RATE=", base_rate)
    print("RVOL_PRIMARY=previous_14_session_mean")
    print("RVOL_SENSITIVITY=previous_20_session_median")
    print("RVOL_COVERAGE=", json.dumps(rvol_coverage))

    return {
        "output_dir": str(out),
        "summary": str(out / "summary.json"),
        "factor_results": str(out / "factor_results.csv"),
        "combo_results": str(out / "combo_results.csv"),
    }
