from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 9132026
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


def _counts(df: pd.DataFrame) -> dict:
    o = _outcome(df["outcome"])
    fav = int((o == "FAVORABLE_FIRST").sum())
    adv = int((o == "ADVERSE_FIRST").sum())
    resolved = fav + adv
    return {
        "events": int(len(df)),
        "resolved": resolved,
        "favorable_first": fav,
        "adverse_first": adv,
        "resolved_rate": float(fav / resolved) if resolved else np.nan,
        "resolution_rate": float(resolved / len(df)) if len(df) else np.nan,
    }


def _classify(lo: float, hi: float) -> str:
    if np.isfinite(lo) and lo > 0:
        return "SUPPORTIVE"
    if np.isfinite(hi) and hi < 0:
        return "NEGATIVE"
    return "CONDITIONAL"


def _cem(
    df: pd.DataFrame,
    eligible_mask: pd.Series,
    treated_mask: pd.Series,
    strata_cols: list[str],
    name: str,
) -> tuple[dict, pd.DataFrame]:
    """Coarsened exact matching using only pre-outcome covariates."""
    select_cols = list(dict.fromkeys(["symbol", "outcome", *strata_cols]))
    x = df.loc[eligible_mask.fillna(False), select_cols].copy()
    x["treated"] = treated_mask.loc[x.index].fillna(False).astype(bool)
    x["outcome"] = _outcome(x["outcome"])
    x["fav"] = (x["outcome"] == "FAVORABLE_FIRST").astype(np.int64)
    x["adv"] = (x["outcome"] == "ADVERSE_FIRST").astype(np.int64)
    x["resolved"] = x["fav"] + x["adv"]

    all_treated = x[x["treated"]]
    treated_all = _counts(all_treated)
    control_all = _counts(x[~x["treated"]])

    grp = (
        x.groupby(strata_cols + ["treated"], dropna=False)
        .agg(events=("outcome", "size"), fav=("fav", "sum"), adv=("adv", "sum"), resolved=("resolved", "sum"))
        .reset_index()
    )
    piv = grp.pivot_table(
        index=strata_cols,
        columns="treated",
        values=["events", "fav", "adv", "resolved"],
        aggfunc="sum",
        fill_value=0,
    )
    piv.columns = [f"{metric}_{'treated' if bool(side) else 'control'}" for metric, side in piv.columns]
    piv = piv.reset_index()
    for c in [
        "events_treated", "events_control", "fav_treated", "fav_control",
        "adv_treated", "adv_control", "resolved_treated", "resolved_control",
    ]:
        if c not in piv.columns:
            piv[c] = 0

    overlap = piv[
        (piv["events_treated"] > 0)
        & (piv["events_control"] > 0)
        & (piv["resolved_treated"] > 0)
        & (piv["resolved_control"] > 0)
    ].copy()

    if overlap.empty:
        result = {
            "test": name,
            "classification": "NO_OVERLAP",
            "strata": "+".join(strata_cols),
            "eligible_events": int(len(x)),
            "eligible_treated_events": treated_all["events"],
            "eligible_treated_resolved": treated_all["resolved"],
            "eligible_treated_rate": treated_all["resolved_rate"],
            "eligible_control_events": control_all["events"],
            "eligible_control_resolved": control_all["resolved"],
            "eligible_control_rate": control_all["resolved_rate"],
            "overlap_strata": 0,
            "matched_treated_events": 0,
            "matched_treated_resolved": 0,
            "treated_event_coverage": 0.0,
            "treated_resolved_coverage": 0.0,
            "treated_rate": np.nan,
            "matched_control_rate": np.nan,
            "lift": np.nan,
            "ci95_lower": np.nan,
            "bootstrap_median": np.nan,
            "ci95_upper": np.nan,
        }
        return result, overlap

    overlap["control_weight"] = overlap["resolved_treated"] / overlap["resolved_control"]
    overlap["control_fav_weighted"] = overlap["fav_control"] * overlap["control_weight"]
    overlap["control_adv_weighted"] = overlap["adv_control"] * overlap["control_weight"]

    tf = float(overlap["fav_treated"].sum())
    ta = float(overlap["adv_treated"].sum())
    cf = float(overlap["control_fav_weighted"].sum())
    ca = float(overlap["control_adv_weighted"].sum())
    tr = tf + ta
    cr = cf + ca
    treat_rate = tf / tr if tr else np.nan
    control_rate = cf / cr if cr else np.nan
    lift = treat_rate - control_rate if np.isfinite(treat_rate) and np.isfinite(control_rate) else np.nan

    if "symbol" not in strata_cols:
        raise ValueError("CEM bootstrap requires symbol in strata_cols")
    sy = (
        overlap.groupby("symbol", dropna=False)
        .agg(
            tf=("fav_treated", "sum"),
            ta=("adv_treated", "sum"),
            cf=("control_fav_weighted", "sum"),
            ca=("control_adv_weighted", "sum"),
        )
        .reset_index()
    )
    all_symbols = np.array(sorted(df["symbol"].astype(str).unique()))
    sy = sy.set_index("symbol").reindex(all_symbols, fill_value=0.0)
    arr = sy[["tf", "ta", "cf", "ca"]].to_numpy(dtype=float)

    rng = np.random.default_rng(SEED)
    vals = np.empty(REPS, dtype=float)
    n_valid = 0
    n_syms = len(all_symbols)
    for _ in range(REPS):
        idx = rng.integers(0, n_syms, size=n_syms)
        stf, sta, scf, sca = arr[idx].sum(axis=0)
        if stf + sta > 0 and scf + sca > 0:
            vals[n_valid] = stf / (stf + sta) - scf / (scf + sca)
            n_valid += 1
    if n_valid:
        lo, med, hi = map(float, np.quantile(vals[:n_valid], [0.025, 0.5, 0.975]))
    else:
        lo = med = hi = np.nan

    matched_treated_events = int(overlap["events_treated"].sum())
    matched_treated_resolved = int(overlap["resolved_treated"].sum())
    result = {
        "test": name,
        "classification": _classify(lo, hi),
        "strata": "+".join(strata_cols),
        "eligible_events": int(len(x)),
        "eligible_treated_events": treated_all["events"],
        "eligible_treated_resolved": treated_all["resolved"],
        "eligible_treated_rate": treated_all["resolved_rate"],
        "eligible_control_events": control_all["events"],
        "eligible_control_resolved": control_all["resolved"],
        "eligible_control_rate": control_all["resolved_rate"],
        "overlap_strata": int(len(overlap)),
        "matched_treated_events": matched_treated_events,
        "matched_treated_resolved": matched_treated_resolved,
        "treated_event_coverage": float(matched_treated_events / treated_all["events"]) if treated_all["events"] else np.nan,
        "treated_resolved_coverage": float(matched_treated_resolved / treated_all["resolved"]) if treated_all["resolved"] else np.nan,
        "treated_rate": float(treat_rate),
        "matched_control_rate": float(control_rate),
        "lift": float(lift),
        "ci95_lower": lo,
        "bootstrap_median": med,
        "ci95_upper": hi,
    }
    return result, overlap


def run(root: Path) -> dict:
    inp = root / "research_outputs" / "pmpd" / "post9n_batch1" / "context_enriched.parquet"
    if not inp.exists():
        raise FileNotFoundError(inp)

    out = root / "research_outputs" / "pmpd" / "edge" / "e1_batch4"
    out.mkdir(parents=True, exist_ok=True)

    v = pd.read_parquet(inp).copy()
    v["outcome"] = _outcome(v["outcome"])
    v["trade_date"] = pd.to_datetime(v["trade_date"]).dt.date
    ts = pd.to_datetime(v["timestamp_et"])
    if getattr(ts.dt, "tz", None) is None:
        v["timestamp_et"] = ts.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
    else:
        v["timestamp_et"] = ts.dt.tz_convert("America/New_York")

    required = {
        "symbol", "direction", "gap_aligned", "overnight_gap_pct",
        "opening_rvol14_mean_5m", "outcome", "timestamp_et",
    }
    missing = sorted(required - set(v.columns))
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    v["event_minute"] = v["timestamp_et"].dt.hour * 60 + v["timestamp_et"].dt.minute
    v["month"] = pd.to_datetime(v["trade_date"]).dt.to_period("M").astype(str)
    v["gap_abs"] = v["overnight_gap_pct"].abs().astype(float)
    v["time30"] = ((v["event_minute"] - SAFE_OPEN_MINUTE) // 30).clip(lower=0).astype("Int64")
    v["time60"] = ((v["event_minute"] - SAFE_OPEN_MINUTE) // 60).clip(lower=0).astype("Int64")

    safe_for_gap = (v["event_minute"] >= SAFE_OPEN_MINUTE) & v["gap_abs"].notna()
    try:
        v["gap_q"] = pd.qcut(v.loc[safe_for_gap, "gap_abs"], 4, labels=False, duplicates="drop").reindex(v.index)
    except ValueError:
        v["gap_q"] = np.nan
    v["gap_q"] = v["gap_q"].astype("Int64")

    safe = (
        (v["event_minute"] >= SAFE_OPEN_MINUTE)
        & v["opening_rvol14_mean_5m"].notna()
        & v["gap_abs"].notna()
        & v["gap_q"].notna()
    )
    high_rvol = v["opening_rvol14_mean_5m"] >= RVOL_THRESHOLD
    gap = v["gap_aligned"].fillna(False).astype(bool)

    primary_eligible = safe & gap
    primary_treated = primary_eligible & high_rvol
    primary, primary_overlap = _cem(
        v,
        primary_eligible,
        primary_treated,
        ["symbol", "direction", "time30", "gap_q"],
        "opening_rvol>=1.5 incremental within gap_aligned (primary CEM)",
    )

    strict, strict_overlap = _cem(
        v,
        primary_eligible,
        primary_treated,
        ["symbol", "direction", "month", "time60", "gap_q"],
        "opening_rvol>=1.5 incremental within gap_aligned (strict month CEM)",
    )

    gap_eligible = safe & high_rvol
    gap_treated = gap_eligible & gap
    gap_incremental, gap_overlap = _cem(
        v,
        gap_eligible,
        gap_treated,
        ["symbol", "direction", "time30", "gap_q"],
        "gap_aligned incremental within opening_rvol>=1.5",
    )

    tests = pd.DataFrame([primary, strict, gap_incremental])
    tests.to_csv(out / "matched_incremental_tests.csv", index=False)
    primary_overlap.to_csv(out / "primary_overlap_strata.csv", index=False)
    strict_overlap.to_csv(out / "strict_overlap_strata.csv", index=False)
    gap_overlap.to_csv(out / "gap_overlap_strata.csv", index=False)

    month_rows = []
    for month in sorted(v.loc[safe, "month"].dropna().unique()):
        mm = v["month"].eq(month)
        res, _ = _cem(
            v,
            primary_eligible & mm,
            primary_treated & mm,
            ["symbol", "direction", "time30", "gap_q"],
            f"primary_{month}",
        )
        month_rows.append({"month": month, **res})
    monthly = pd.DataFrame(month_rows)
    monthly.to_csv(out / "monthly_matched_robustness.csv", index=False)

    direction_rows = []
    for direction in ["BULL", "BEAR"]:
        dm = v["direction"].astype(str).str.upper().eq(direction)
        res, _ = _cem(
            v,
            primary_eligible & dm,
            primary_treated & dm,
            ["symbol", "direction", "time30", "gap_q"],
            f"primary_{direction}",
        )
        direction_rows.append({"direction": direction, **res})
    directions = pd.DataFrame(direction_rows)
    directions.to_csv(out / "direction_matched_robustness.csv", index=False)

    valid_months = monthly[np.isfinite(monthly["lift"].astype(float))].copy() if len(monthly) else monthly
    valid_dirs = directions[np.isfinite(directions["lift"].astype(float))].copy() if len(directions) else directions

    summary = {
        "step": "PMPD-EDGE-E1-B4",
        "purpose": "Matched-control and incremental-information audit of the frozen opening-RVOL hypothesis.",
        "input": str(inp),
        "frozen_threshold": RVOL_THRESHOLD,
        "safe_availability_rule": "opening 09:30-09:34 RVOL usable only for events at/after 09:35 ET",
        "primary_estimand": "Among signal-time-safe gap-aligned events, incremental resolved favorable-first lift associated with opening RVOL14 mean >=1.5 after coarsened exact matching on symbol, direction, event-time bin and overnight-gap magnitude quartile.",
        "primary": primary,
        "strict_month_sensitivity": strict,
        "gap_incremental_secondary": gap_incremental,
        "robustness": {
            "months_with_positive_matched_lift": int((valid_months["lift"] > 0).sum()) if len(valid_months) else 0,
            "months_tested": int(len(valid_months)),
            "directions_with_positive_matched_lift": int((valid_dirs["lift"] > 0).sum()) if len(valid_dirs) else 0,
            "directions_tested": int(len(valid_dirs)),
        },
        "governance": {
            "research_only": True,
            "2026_is_development_evidence": True,
            "v5_modified": False,
            "threshold_retuned": False,
            "production_rule_authorized": False,
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print("OUTPUT_DIR=", out)
    print("PRIMARY_CLASSIFICATION=", primary["classification"])
    print("PRIMARY_MATCHED_TREATED_RATE=", primary["treated_rate"])
    print("PRIMARY_MATCHED_CONTROL_RATE=", primary["matched_control_rate"])
    print("PRIMARY_MATCHED_LIFT=", primary["lift"])
    print("PRIMARY_MATCHED_LIFT_CI=", [primary["ci95_lower"], primary["ci95_upper"]])
    print("PRIMARY_TREATED_RESOLVED_COVERAGE=", primary["treated_resolved_coverage"])
    print("STRICT_MONTH_CLASSIFICATION=", strict["classification"])
    print("GAP_INCREMENTAL_CLASSIFICATION=", gap_incremental["classification"])
    print("MONTHS_POSITIVE_MATCHED_LIFT=", summary["robustness"]["months_with_positive_matched_lift"], "/", summary["robustness"]["months_tested"])
    print("DIRECTIONS_POSITIVE_MATCHED_LIFT=", summary["robustness"]["directions_with_positive_matched_lift"], "/", summary["robustness"]["directions_tested"])

    return {
        "output_dir": str(out),
        "summary": str(out / "summary.json"),
        "matched_tests": str(out / "matched_incremental_tests.csv"),
        "monthly": str(out / "monthly_matched_robustness.csv"),
        "directions": str(out / "direction_matched_robustness.csv"),
    }
