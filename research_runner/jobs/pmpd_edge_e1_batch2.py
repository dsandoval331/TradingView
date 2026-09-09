from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 9112026
REPS = 10000
PRIMARY_RVOL_THRESHOLD = 1.5
SECONDARY_RVOL_THRESHOLD = 2.0
SAFE_OPEN_MINUTE = 9 * 60 + 35  # full 09:30-09:34 opening 5m bar is known by 09:35 ET


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


def _cluster_boot_lift(df: pd.DataFrame, mask: pd.Series, base_rate: float) -> tuple[float, float, float]:
    g = df.loc[mask.fillna(False), ["symbol", "outcome"]].copy()
    if g.empty or not np.isfinite(base_rate):
        return (np.nan, np.nan, np.nan)

    g["outcome"] = _outcome(g["outcome"])
    g["fav"] = (g["outcome"] == "FAVORABLE_FIRST").astype(np.int64)
    g["adv"] = (g["outcome"] == "ADVERSE_FIRST").astype(np.int64)

    syms = np.array(sorted(df["symbol"].astype(str).unique()))
    counts = (
        g.groupby("symbol")[["fav", "adv"]]
        .sum()
        .reindex(syms, fill_value=0)
        .to_numpy(dtype=np.int64)
    )

    rng = np.random.default_rng(SEED)
    vals = np.empty(REPS, dtype=float)
    n_valid = 0
    n_syms = len(syms)
    for _ in range(REPS):
        idx = rng.integers(0, n_syms, size=n_syms)
        fav, adv = counts[idx].sum(axis=0)
        if fav + adv:
            vals[n_valid] = fav / (fav + adv) - base_rate
            n_valid += 1

    if not n_valid:
        return (np.nan, np.nan, np.nan)
    return tuple(map(float, np.quantile(vals[:n_valid], [0.025, 0.5, 0.975])))


def _test(df: pd.DataFrame, mask: pd.Series, base_rate: float, name: str) -> dict:
    st = _stats(df.loc[mask.fillna(False)])
    lo, med, hi = _cluster_boot_lift(df, mask, base_rate)
    return {
        "test": name,
        **st,
        "lift_vs_safe_cohort": float(st["rate"] - base_rate) if np.isfinite(st["rate"]) else np.nan,
        "lift_ci95_lower": lo,
        "lift_bootstrap_median": med,
        "lift_ci95_upper": hi,
    }


def run(root: Path) -> dict:
    inp = root / "research_outputs" / "pmpd" / "post9n_batch1" / "context_enriched.parquet"
    if not inp.exists():
        raise FileNotFoundError(inp)

    out = root / "research_outputs" / "pmpd" / "edge" / "e1_batch2"
    out.mkdir(parents=True, exist_ok=True)

    v = pd.read_parquet(inp).copy()
    v["outcome"] = _outcome(v["outcome"])
    v["trade_date"] = pd.to_datetime(v["trade_date"]).dt.date
    v["timestamp_et"] = pd.to_datetime(v["timestamp_et"], utc=True).dt.tz_convert("America/New_York") if pd.api.types.is_datetime64_any_dtype(v["timestamp_et"]) and getattr(v["timestamp_et"].dt, "tz", None) is not None and str(v["timestamp_et"].dt.tz) == "UTC" else pd.to_datetime(v["timestamp_et"])
    v["event_minute"] = v["timestamp_et"].dt.hour * 60 + v["timestamp_et"].dt.minute
    v["month"] = pd.to_datetime(v["trade_date"]).dt.to_period("M").astype(str)

    required = {"symbol", "direction", "gap_aligned", "opening_rvol14_mean_5m", "outcome", "event_minute"}
    missing = sorted(required - set(v.columns))
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    full = _stats(v)
    safe_mask = (v["event_minute"] >= SAFE_OPEN_MINUTE) & v["opening_rvol14_mean_5m"].notna()
    safe = v.loc[safe_mask].copy()
    safe_stats = _stats(safe)
    safe_rate = safe_stats["rate"]

    primary_mask = safe_mask & v["gap_aligned"].fillna(False) & (v["opening_rvol14_mean_5m"] >= PRIMARY_RVOL_THRESHOLD)
    primary_nogap_mask = safe_mask & (v["opening_rvol14_mean_5m"] >= PRIMARY_RVOL_THRESHOLD)
    secondary_mask = safe_mask & v["gap_aligned"].fillna(False) & (v["opening_rvol14_mean_5m"] >= SECONDARY_RVOL_THRESHOLD)
    secondary_nogap_mask = safe_mask & (v["opening_rvol14_mean_5m"] >= SECONDARY_RVOL_THRESHOLD)

    tests = [
        _test(v, primary_mask, safe_rate, "SAFE gap_aligned + opening_rvol14_mean>=1.5"),
        _test(v, primary_nogap_mask, safe_rate, "SAFE opening_rvol14_mean>=1.5"),
        _test(v, secondary_mask, safe_rate, "SAFE gap_aligned + opening_rvol14_mean>=2.0"),
        _test(v, secondary_nogap_mask, safe_rate, "SAFE opening_rvol14_mean>=2.0"),
    ]
    tests_df = pd.DataFrame(tests)
    tests_df.to_csv(out / "causal_tests.csv", index=False)

    # Directional robustness for the frozen primary Batch-1 hypothesis.
    direction_rows = []
    for direction in ["BULL", "BEAR"]:
        dmask = v["direction"].astype(str).str.upper().eq(direction)
        base = _stats(v.loc[safe_mask & dmask])
        sel_mask = primary_mask & dmask
        sel = _stats(v.loc[sel_mask])
        lo, med, hi = _cluster_boot_lift(v.loc[dmask].copy(), sel_mask.loc[dmask], base["rate"])
        direction_rows.append({
            "direction": direction,
            "safe_events": base["events"],
            "safe_resolved": base["resolved"],
            "safe_rate": base["rate"],
            "selected_events": sel["events"],
            "selected_resolved": sel["resolved"],
            "selected_rate": sel["rate"],
            "lift": float(sel["rate"] - base["rate"]) if np.isfinite(sel["rate"]) and np.isfinite(base["rate"]) else np.nan,
            "lift_ci95_lower": lo,
            "lift_bootstrap_median": med,
            "lift_ci95_upper": hi,
        })
    pd.DataFrame(direction_rows).to_csv(out / "direction_robustness.csv", index=False)

    # Monthly robustness: compare selected primary cohort with same-month safe cohort.
    month_rows = []
    for month in sorted(v["month"].dropna().unique()):
        mm = v["month"].eq(month)
        base = _stats(v.loc[safe_mask & mm])
        sel = _stats(v.loc[primary_mask & mm])
        month_rows.append({
            "month": month,
            "safe_resolved": base["resolved"],
            "safe_rate": base["rate"],
            "selected_events": sel["events"],
            "selected_resolved": sel["resolved"],
            "selected_rate": sel["rate"],
            "lift": float(sel["rate"] - base["rate"]) if np.isfinite(sel["rate"]) and np.isfinite(base["rate"]) else np.nan,
        })
    monthly = pd.DataFrame(month_rows)
    monthly.to_csv(out / "monthly_robustness.csv", index=False)

    # Leave-one-month-out robustness against the safe-cohort baseline in the remaining sample.
    lomo_rows = []
    for month in sorted(v["month"].dropna().unique()):
        keep = ~v["month"].eq(month)
        base = _stats(v.loc[safe_mask & keep])
        sel = _stats(v.loc[primary_mask & keep])
        lomo_rows.append({
            "left_out_month": month,
            "safe_resolved": base["resolved"],
            "safe_rate": base["rate"],
            "selected_resolved": sel["resolved"],
            "selected_rate": sel["rate"],
            "lift": float(sel["rate"] - base["rate"]) if np.isfinite(sel["rate"]) and np.isfinite(base["rate"]) else np.nan,
        })
    lomo = pd.DataFrame(lomo_rows)
    lomo.to_csv(out / "leave_one_month_out.csv", index=False)

    # Symbol breadth for the frozen primary hypothesis.
    symbol_rows = []
    for sym in sorted(v["symbol"].astype(str).unique()):
        sm = v["symbol"].astype(str).eq(sym)
        base = _stats(v.loc[safe_mask & sm])
        sel = _stats(v.loc[primary_mask & sm])
        symbol_rows.append({
            "symbol": sym,
            "safe_resolved": base["resolved"],
            "safe_rate": base["rate"],
            "selected_resolved": sel["resolved"],
            "selected_rate": sel["rate"],
            "lift": float(sel["rate"] - base["rate"]) if np.isfinite(sel["rate"]) and np.isfinite(base["rate"]) else np.nan,
        })
    symbols = pd.DataFrame(symbol_rows)
    symbols.to_csv(out / "symbol_robustness.csv", index=False)

    breadth = symbols[symbols["selected_resolved"] >= 10].copy()
    monthly_valid = monthly[monthly["selected_resolved"] > 0].copy()
    lomo_valid = lomo[lomo["selected_resolved"] > 0].copy()

    primary = tests[0]
    summary = {
        "step": "PMPD-EDGE-E1-B2",
        "purpose": "Causal availability audit and robustness decomposition of the frozen Batch-1 primary RVOL hypothesis.",
        "input": str(inp),
        "governance": {
            "research_only": True,
            "2026_is_development_evidence": True,
            "v5_modified": False,
            "batch1_threshold_retuned": False,
            "production_rule_authorized": False,
        },
        "availability_rule": "Full 09:30-09:34 opening 5m volume is considered signal-time available only for events timestamped at or after 09:35 ET.",
        "primary_hypothesis": "gap_aligned + opening_rvol14_mean_5m >= 1.5",
        "full_population": full,
        "safe_cohort": safe_stats,
        "primary_safe_result": primary,
        "robustness": {
            "months_positive_lift": int((monthly_valid["lift"] > 0).sum()),
            "months_tested": int(len(monthly_valid)),
            "leave_one_month_out_positive_lift": int((lomo_valid["lift"] > 0).sum()),
            "leave_one_month_out_tests": int(len(lomo_valid)),
            "symbols_with_at_least_10_selected_resolved": int(len(breadth)),
            "fraction_eligible_symbols_positive_lift": float((breadth["lift"] > 0).mean()) if len(breadth) else np.nan,
            "fraction_eligible_symbols_selected_rate_gt_0_50": float((breadth["selected_rate"] > 0.50).mean()) if len(breadth) else np.nan,
        },
        "secondary_threshold_note": ">=2.0 is exploratory/secondary because Batch 1 already exposed its result; it is not a newly untouched threshold test.",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print("OUTPUT_DIR=", out)
    print("SAFE_COHORT_RATE=", safe_rate)
    print("PRIMARY_SAFE_RATE=", primary["rate"])
    print("PRIMARY_SAFE_LIFT=", primary["lift_vs_safe_cohort"])
    print("PRIMARY_SAFE_LIFT_CI=", [primary["lift_ci95_lower"], primary["lift_ci95_upper"]])
    print("MONTHS_POSITIVE_LIFT=", summary["robustness"]["months_positive_lift"], "/", summary["robustness"]["months_tested"])
    print("LOMO_POSITIVE_LIFT=", summary["robustness"]["leave_one_month_out_positive_lift"], "/", summary["robustness"]["leave_one_month_out_tests"])
    print("ELIGIBLE_SYMBOLS=", summary["robustness"]["symbols_with_at_least_10_selected_resolved"])
    print("SYMBOL_FRACTION_POSITIVE_LIFT=", summary["robustness"]["fraction_eligible_symbols_positive_lift"])

    return {
        "output_dir": str(out),
        "summary": str(out / "summary.json"),
        "causal_tests": str(out / "causal_tests.csv"),
        "direction_robustness": str(out / "direction_robustness.csv"),
        "monthly_robustness": str(out / "monthly_robustness.csv"),
        "leave_one_month_out": str(out / "leave_one_month_out.csv"),
        "symbol_robustness": str(out / "symbol_robustness.csv"),
    }
