from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

PROTOCOL = "PMPD_EDGE_E2_ACCEPTANCE_PROTOCOL_V1"
FAV = 0.005
ADV = 0.005
SEED = 9152026
REPS = 10000
EXECUTABLE_STATES = ["close_acceptance", "hold_acceptance", "retest_acceptance", "reclaim_after_failure"]
DESCRIPTIVE_STATES = ["failed_acceptance"]


def _load_cache(cache: Path, sym: str) -> pd.DataFrame:
    p = cache / sym / f"{sym}_2026.parquet"
    if not p.exists():
        raise FileNotFoundError(p)
    d = pd.read_parquet(p).copy()
    ts_col = next((c for c in ["timestamp_utc", "timestamp", "datetime_utc", "ts_utc"] if c in d.columns), None)
    if ts_col is None:
        raise KeyError(f"{sym}: timestamp column not found")
    d["timestamp_utc"] = pd.to_datetime(d[ts_col], utc=True)
    d["timestamp_et"] = d["timestamp_utc"].dt.tz_convert("America/New_York")
    d["trade_date"] = d["timestamp_et"].dt.date
    h = next((c for c in ["high", "h", "High"] if c in d.columns), None)
    l = next((c for c in ["low", "l", "Low"] if c in d.columns), None)
    if not h or not l:
        raise KeyError(f"{sym}: high/low columns not found")
    return d.rename(columns={h: "_high", l: "_low"})


def _outcome(direction: str, entry: float, after: pd.DataFrame) -> tuple[str, float | None]:
    if after.empty or not np.isfinite(entry) or entry <= 0:
        return "UNRESOLVED", None
    if direction == "BULL":
        fav_level, adv_level = entry * (1 + FAV), entry * (1 - ADV)
        fav_hit = after["_high"].astype(float) >= fav_level
        adv_hit = after["_low"].astype(float) <= adv_level
    else:
        fav_level, adv_level = entry * (1 - FAV), entry * (1 + ADV)
        fav_hit = after["_low"].astype(float) <= fav_level
        adv_hit = after["_high"].astype(float) >= adv_level
    hits = after[fav_hit | adv_hit]
    if hits.empty:
        return "UNRESOLVED", None
    first = hits.iloc[0]
    i = first.name
    f = bool(fav_hit.loc[i])
    a = bool(adv_hit.loc[i])
    label = "AMBIGUOUS_SAME_BAR" if f and a else ("FAVORABLE_FIRST" if f else "ADVERSE_FIRST")
    return label, float((first["timestamp_et"] + pd.Timedelta(minutes=1)).timestamp())


def _stats(df: pd.DataFrame, col: str) -> dict:
    s = df[col].astype(str)
    fav = int((s == "FAVORABLE_FIRST").sum())
    adv = int((s == "ADVERSE_FIRST").sum())
    amb = int((s == "AMBIGUOUS_SAME_BAR").sum())
    unr = int((s == "UNRESOLVED").sum())
    resolved = fav + adv
    return {"events": int(len(df)), "resolved": resolved, "favorable": fav, "adverse": adv, "ambiguous": amb, "unresolved": unr,
            "rate": float(fav / resolved) if resolved else np.nan}


def _cluster_boot(df: pd.DataFrame, state_col: str, base_col: str) -> tuple[float, float, float]:
    syms = np.array(sorted(df["symbol"].astype(str).unique()))
    def counts(col: str):
        x = df[["symbol", col]].copy()
        x["fav"] = (x[col] == "FAVORABLE_FIRST").astype(np.int64)
        x["adv"] = (x[col] == "ADVERSE_FIRST").astype(np.int64)
        return x.groupby("symbol")[["fav", "adv"]].sum().reindex(syms, fill_value=0).to_numpy(dtype=np.int64)
    a = counts(state_col)
    b = counts(base_col)
    rng = np.random.default_rng(SEED)
    vals = []
    for _ in range(REPS):
        idx = rng.integers(0, len(syms), size=len(syms))
        af, aa = a[idx].sum(axis=0)
        bf, ba = b[idx].sum(axis=0)
        if af + aa and bf + ba:
            vals.append(af / (af + aa) - bf / (bf + ba))
    return tuple(map(float, np.quantile(vals, [0.025, 0.5, 0.975]))) if vals else (np.nan, np.nan, np.nan)


def run(root: Path) -> dict:
    paths_p = root / "research_outputs" / "pmpd" / "edge" / "e2_batch2" / "acceptance_state_paths.parquet"
    context_p = root / "research_outputs" / "pmpd" / "post9n_batch1" / "context_enriched.parquet"
    protocol_p = root / "research_outputs" / "pmpd" / "edge" / "e2_batch1" / "acceptance_protocol.json"
    cache = root / "data" / "second1m_alt_entry_cache_v1" / "partitions"
    for p in [paths_p, context_p, protocol_p]:
        if not p.exists():
            raise FileNotFoundError(p)
    protocol = json.loads(protocol_p.read_text())
    if protocol.get("protocol") != PROTOCOL:
        raise RuntimeError("protocol mismatch")

    paths = pd.read_parquet(paths_p).copy()
    ctx = pd.read_parquet(context_p).copy()
    ts = pd.to_datetime(ctx["timestamp_et"])
    if getattr(ts.dt, "tz", None) is None:
        ctx["timestamp_et"] = ts.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
    else:
        ctx["timestamp_et"] = ts.dt.tz_convert("America/New_York")
    ctx["trade_date"] = pd.to_datetime(ctx["trade_date"]).dt.date
    ctx["direction"] = ctx["direction"].astype(str).str.upper().str.strip()
    ctx["event_key"] = ctx["symbol"].astype(str) + "|" + ctx["trade_date"].astype(str) + "|" + ctx["timestamp_et"].astype(str) + "|" + ctx["direction"]
    base_cols = ["event_key", "outcome"]
    if "opening_rvol14_mean_5m" in ctx.columns:
        base_cols.append("opening_rvol14_mean_5m")
    x = paths.merge(ctx[base_cols].drop_duplicates("event_key"), on="event_key", how="left", suffixes=("", "_ctx"))
    x["dp4_outcome"] = x["outcome"].astype(str).str.upper().str.strip().replace({"BOTH":"AMBIGUOUS_SAME_BAR","NEITHER":"UNRESOLVED"})

    state_cols = EXECUTABLE_STATES + DESCRIPTIVE_STATES
    for state in state_cols:
        x[f"{state}_outcome"] = "NOT_SEEN"
        x[f"{state}_hit_timestamp_epoch"] = np.nan

    for sym, idx in x.groupby("symbol").groups.items():
        d = _load_cache(cache, str(sym))
        for i in idx:
            row = x.loc[i]
            day = row["trade_date"]
            daybars = d[d["trade_date"] == day]
            direction = str(row["direction"]).upper()
            for state in state_cols:
                if not bool(row.get(f"{state}_seen", False)):
                    continue
                t = pd.to_datetime(row.get(f"{state}_time"))
                if pd.isna(t):
                    continue
                if t.tzinfo is None:
                    t = t.tz_localize("America/New_York")
                else:
                    t = t.tz_convert("America/New_York")
                entry = float(row.get(f"{state}_price", np.nan))
                # Outcome starts strictly after the completed bar that made the state observable.
                after = daybars[(daybars["timestamp_et"] + pd.Timedelta(minutes=1)) > t]
                label, hit_ts = _outcome(direction, entry, after)
                x.at[i, f"{state}_outcome"] = label
                if hit_ts is not None:
                    x.at[i, f"{state}_hit_timestamp_epoch"] = hit_ts

    outdir = root / "research_outputs" / "pmpd" / "edge" / "e2_batch3"
    outdir.mkdir(parents=True, exist_ok=True)
    x.to_parquet(outdir / "state_anchored_outcomes.parquet", index=False)

    rows = []
    for state in EXECUTABLE_STATES:
        m = x[f"{state}_seen"].fillna(False)
        g = x[m].copy()
        if g.empty:
            continue
        s = _stats(g, f"{state}_outcome")
        b = _stats(g, "dp4_outcome")
        lo, med, hi = _cluster_boot(g, f"{state}_outcome", "dp4_outcome")
        delay = pd.to_numeric(g.get(f"{state}_minutes_from_dp4"), errors="coerce")
        move = pd.to_numeric(g.get(f"{state}_distance_pct"), errors="coerce")
        rows.append({
            "state": state, **s,
            "dp4_same_cohort_rate": b["rate"],
            "lift_vs_dp4_same_cohort": (s["rate"] - b["rate"]) if np.isfinite(s["rate"]) and np.isfinite(b["rate"]) else np.nan,
            "ci95_lower": lo, "bootstrap_median": med, "ci95_upper": hi,
            "coverage_vs_analyzable": float(len(g) / max(1, int(x["analyzable"].fillna(False).sum()))),
            "median_delay_minutes": float(delay.median()) if delay.notna().any() else np.nan,
            "median_directional_move_at_decision_pct": float(move.median()) if move.notna().any() else np.nan,
        })
    comp = pd.DataFrame(rows)
    comp.to_csv(outdir / "state_comparison.csv", index=False)

    # Prespecified context split only: frozen opening RVOL >=1.5, no threshold retuning.
    rvol_rows = []
    for state in EXECUTABLE_STATES:
        seen = x[f"{state}_seen"].fillna(False)
        for tag, mask in [("rvol_ge_1_5", x["opening_rvol_ge_1_5"].fillna(False)), ("rvol_lt_1_5_or_unavailable", ~x["opening_rvol_ge_1_5"].fillna(False))]:
            g = x[seen & mask]
            if len(g):
                st = _stats(g, f"{state}_outcome")
                rvol_rows.append({"state": state, "context": tag, **st})
    pd.DataFrame(rvol_rows).to_csv(outdir / "opening_rvol_context.csv", index=False)

    summary = {
        "step": "PMPD-EDGE-E2-B3",
        "protocol": PROTOCOL,
        "purpose": "Pre-specified state-anchored +/-0.50% outcome comparison from each executable acceptance state's first observable completed-bar decision timestamp/price.",
        "favorable_target_pct": FAV,
        "adverse_target_pct": ADV,
        "bootstrap_reps": REPS,
        "bootstrap_seed": SEED,
        "executable_states": EXECUTABLE_STATES,
        "penetration_outcome_tested": False,
        "penetration_reason": "B2 penetration price is an intraminute extreme observed only at minute completion and is not treated as an executable fill price.",
        "comparison_rows": comp.to_dict(orient="records"),
        "guardrails": {
            "research_only": True, "2026_development_evidence": True, "v4_modified": False, "v5_modified": False,
            "production_rule_authorized": False, "acceptance_definitions_retuned": False, "rvol_threshold_retuned": False,
            "trade_health_reserved_for_e3": True,
        },
        "next_batch_if_warranted": "E2-B4 robustness and temporal/symbol concentration audit of any acceptance state showing practically meaningful improvement after delay/coverage costs.",
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return {"status":"PASS","protocol":PROTOCOL,"output_paths":[
        str((outdir/"state_anchored_outcomes.parquet").relative_to(root)),
        str((outdir/"state_comparison.csv").relative_to(root)),
        str((outdir/"opening_rvol_context.csv").relative_to(root)),
        str((outdir/"summary.json").relative_to(root)),
    ],"research_only":True,"v4_modified":False,"v5_modified":False,"production_rule_authorized":False}
