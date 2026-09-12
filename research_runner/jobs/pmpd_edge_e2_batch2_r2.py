from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research_runner.jobs import pmpd_edge_e2_batch2 as b2

PROTOCOL = b2.PROTOCOL
START = b2.START
END = b2.END


def _raw_stack_boundary(d: pd.DataFrame, day, direction: str) -> tuple[float, dict]:
    h = b2._find_col(d.columns, ["high", "h", "High"])
    l = b2._find_col(d.columns, ["low", "l", "Low"])
    if not h or not l:
        return np.nan, {"reason": "ohlc_missing"}

    t = d["timestamp_et"].dt.time
    pm = d[(d["trade_date"] == day) & (t >= pd.Timestamp("04:00").time()) & (t <= pd.Timestamp("09:29").time())]
    prior_dates = sorted(x for x in d.loc[d["trade_date"] < day, "trade_date"].dropna().unique())
    if not prior_dates or pm.empty:
        return np.nan, {"reason": "pm_or_prior_date_missing"}

    # Frozen V5 uses the immediately preceding observed trading date for prior RTH/AH context.
    prior = prior_dates[-1]
    prev = d[d["trade_date"] == prior]
    pt = prev["timestamp_et"].dt.time
    rth = prev[(pt >= pd.Timestamp("09:30").time()) & (pt <= pd.Timestamp("15:59").time())]
    ah = prev[(pt >= pd.Timestamp("16:00").time()) & (pt <= pd.Timestamp("19:59").time())]
    if rth.empty or ah.empty:
        return np.nan, {"reason": "prior_rth_or_ah_missing", "prior_date": str(prior)}

    levels = {
        "pmh": float(pm[h].max()),
        "pml": float(pm[l].min()),
        "pdh": float(rth[h].max()),
        "pdl": float(rth[l].min()),
        "ahh": float(ah[h].max()),
        "ahl": float(ah[l].min()),
        "prior_date": str(prior),
    }
    if direction == "BULL":
        boundary = max(levels["pmh"], levels["ahh"], levels["pdh"])
    else:
        boundary = min(levels["pml"], levels["ahl"], levels["pdl"])
    return float(boundary), levels


def run(root: Path) -> dict:
    inp = root / "research_outputs" / "pmpd" / "post9n_batch1" / "context_enriched.parquet"
    protocol_path = root / "research_outputs" / "pmpd" / "edge" / "e2_batch1" / "acceptance_protocol.json"
    cache = root / "data" / "second1m_alt_entry_cache_v1" / "partitions"
    for p in [inp, protocol_path, cache]:
        if not p.exists():
            raise FileNotFoundError(p)

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("protocol") != PROTOCOL:
        raise RuntimeError(f"Frozen protocol mismatch: {protocol.get('protocol')}")

    outdir = root / "research_outputs" / "pmpd" / "edge" / "e2_batch2_r2"
    outdir.mkdir(parents=True, exist_ok=True)

    v = pd.read_parquet(inp).copy()
    v["trade_date"] = pd.to_datetime(v["trade_date"]).dt.date
    v = v[v["trade_date"].between(START, END)].copy()
    ts = pd.to_datetime(v["timestamp_et"])
    if getattr(ts.dt, "tz", None) is None:
        v["timestamp_et"] = ts.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
    else:
        v["timestamp_et"] = ts.dt.tz_convert("America/New_York")
    v = v[v["timestamp_et"].notna()].copy()
    v["direction"] = v["direction"].astype(str).str.upper().str.strip()
    v["event_key"] = v["symbol"].astype(str) + "|" + v["trade_date"].astype(str) + "|" + v["timestamp_et"].astype(str) + "|" + v["direction"]

    rows = []
    missing_cache = []
    symbol_errors = []
    boundary_reason_counts: dict[str, int] = {}
    for n, sym in enumerate(sorted(v["symbol"].astype(str).unique()), 1):
        print(f"[{n}/112] E2_ACCEPTANCE_PATH_R2 {sym}")
        d = b2._load_cache(cache, sym)
        if d is None:
            missing_cache.append(sym)
            continue
        try:
            minutes, bars, _ = b2._prepare_symbol(d)
        except Exception as exc:
            symbol_errors.append({"symbol": sym, "error": repr(exc)})
            continue

        for _, er in v[v["symbol"].astype(str).eq(sym)].iterrows():
            boundary, level_meta = _raw_stack_boundary(d, er["trade_date"], er["direction"])
            reason = "raw_six_level_stack" if np.isfinite(boundary) else str(level_meta.get("reason", "unresolved"))
            boundary_reason_counts[reason] = boundary_reason_counts.get(reason, 0) + 1
            base = {
                "event_key": er["event_key"], "symbol": sym, "trade_date": er["trade_date"],
                "direction": er["direction"], "dp4_timestamp_et": er["timestamp_et"],
                "acceptance_boundary": boundary, "boundary_source": reason,
                "pmh": level_meta.get("pmh"), "pml": level_meta.get("pml"),
                "ahh": level_meta.get("ahh"), "ahl": level_meta.get("ahl"),
                "pdh": level_meta.get("pdh"), "pdl": level_meta.get("pdl"),
                "prior_trade_date": level_meta.get("prior_date"),
                "opening_rvol14_mean_5m": er.get("opening_rvol14_mean_5m", np.nan),
                "opening_rvol_ge_1_5": bool(er.get("opening_rvol14_mean_5m", np.nan) >= 1.5) if pd.notna(er.get("opening_rvol14_mean_5m", np.nan)) else False,
            }
            if not np.isfinite(boundary):
                base.update({"analyzable": False, "analysis_reason": reason})
                rows.append(base)
                continue
            path = b2._event_path(er, minutes, bars, boundary)
            base.update({"analyzable": True, "analysis_reason": "ok"})
            for state in ["penetration", "close_acceptance", "hold_acceptance", "retest_acceptance", "failed_acceptance", "reclaim_after_failure"]:
                m = path.get(state)
                base[f"{state}_seen"] = m is not None
                if m:
                    for k, val in m.items():
                        base[f"{state}_{k}"] = val
            rows.append(base)

    paths = pd.DataFrame(rows)
    states = ["penetration", "close_acceptance", "hold_acceptance", "retest_acceptance", "failed_acceptance", "reclaim_after_failure"]
    for state in states:
        col = f"{state}_seen"
        if col not in paths.columns:
            paths[col] = False
        paths[col] = paths[col].fillna(False).astype(bool)
    paths.to_parquet(outdir / "acceptance_state_paths.parquet", index=False)

    analyzable = paths[paths["analyzable"].fillna(False)]
    coverage_rows = [
        {"metric": "context_events", "count": len(v), "rate": 1.0},
        {"metric": "rows_emitted", "count": len(paths), "rate": len(paths) / len(v) if len(v) else np.nan},
        {"metric": "boundary_resolved", "count": len(analyzable), "rate": len(analyzable) / len(v) if len(v) else np.nan},
        {"metric": "analyzable", "count": len(analyzable), "rate": len(analyzable) / len(v) if len(v) else np.nan},
    ]
    for state in states:
        seen = int(analyzable[f"{state}_seen"].sum())
        coverage_rows.append({"metric": state, "count": seen, "rate": seen / len(analyzable) if len(analyzable) else np.nan})
    pd.DataFrame(coverage_rows).to_csv(outdir / "coverage.csv", index=False)

    delays = []
    for state in states:
        col = f"{state}_minutes_from_dp4"
        vals = pd.to_numeric(analyzable[col], errors="coerce").dropna() if col in analyzable.columns else pd.Series(dtype=float)
        delays.append({"state": state, "n": len(vals), "median_minutes": vals.median() if len(vals) else np.nan,
                       "p25_minutes": vals.quantile(.25) if len(vals) else np.nan, "p75_minutes": vals.quantile(.75) if len(vals) else np.nan,
                       "p90_minutes": vals.quantile(.90) if len(vals) else np.nan})
    pd.DataFrame(delays).to_csv(outdir / "decision_delay.csv", index=False)

    schema = {"boundary_method": "raw canonical 1m: current PM 04:00-09:29 ET + immediately prior observed trading-date RTH 09:30-15:59 ET + AH 16:00-19:59 ET",
              "boundary_reason_counts": boundary_reason_counts, "missing_cache_symbols": missing_cache, "symbol_errors": symbol_errors}
    (outdir / "schema_audit.json").write_text(json.dumps(schema, indent=2, default=str), encoding="utf-8")

    summary = {
        "step": "PMPD-EDGE-E2-B2-R2", "protocol": PROTOCOL,
        "supersedes_invalid_execution_job": "e2aa88ff-aaf2-4120-abca-7c8b56d2ece1",
        "integrity_fix": "context artifact omitted PM/AH/PD level columns; derive frozen six-level stack directly from governed canonical raw 1m cache",
        "taxonomy_changed": False, "outcome_comparison_performed": False,
        "context_events": int(len(v)), "rows_emitted": int(len(paths)), "symbols_context": int(v["symbol"].nunique()),
        "boundary_resolved_events": int(len(analyzable)), "analyzable_events": int(len(analyzable)),
        "state_counts": {s: int(analyzable[f"{s}_seen"].sum()) for s in states},
        "boundary_reason_counts": boundary_reason_counts, "symbols_missing_cache": missing_cache, "symbol_errors": symbol_errors,
        "guardrails": {"research_only": True, "2026_development_evidence": True, "v4_modified": False, "v5_modified": False,
                       "production_rule_authorized": False, "trade_health_reserved_for_e3": True, "acceptance_definitions_retuned": False},
        "next_batch_if_integrity_passes": "E2-B3 pre-specified state-anchored +/-0.50% outcome comparison from each state's first observable decision timestamp/price.",
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print("PMPD_EDGE_E2_B2_R2_SUMMARY=" + json.dumps(summary, sort_keys=True, default=str))

    outputs = ["acceptance_state_paths.parquet", "coverage.csv", "decision_delay.csv", "schema_audit.json", "summary.json"]
    return {"status": "PASS", "protocol": PROTOCOL, "context_events": len(v), "analyzable_events": len(analyzable),
            "outcome_comparison_performed": False, "output_paths": [str((outdir / f).relative_to(root)) for f in outputs],
            "research_only": True, "v4_modified": False, "v5_modified": False, "production_rule_authorized": False}
