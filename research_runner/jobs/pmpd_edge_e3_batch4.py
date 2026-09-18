from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

PROTOCOL = "PMPD_EDGE_E3_TRADE_HEALTH_PROTOCOL_V1"
EXPECTED_ROWS = 2_005_639
VALID_DIRECTIONS = {"BULL", "BEAR"}

def _load(root: Path) -> pd.DataFrame:
    d = root / "research_outputs/pmpd/edge/e3_batch3"
    parts = sorted(d.glob("trade_health_associations_part_*.parquet"))
    if len(parts) != 16:
        raise RuntimeError(f"expected 16 E3-B3 shards, found {len(parts)}")
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)

def _rate_table(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    x = df[df.first_passage.isin(["FAVORABLE_FIRST","ADVERSE_FIRST"])].copy()
    x["fav"] = (x.first_passage == "FAVORABLE_FIRST").astype(int)
    if x.empty:
        return pd.DataFrame()
    z = x.groupby(keys, dropna=False).agg(
        resolved_events=("event_key","size"),
        unique_trades=("event_key","nunique"),
        symbols=("symbol","nunique"),
        favorable_first=("fav","sum"),
        median_subsequent_mfe_pct=("subsequent_mfe_pct","median"),
        median_subsequent_mae_pct=("subsequent_mae_pct","median"),
        median_minutes_to_first_passage=("minutes_to_first_passage","median"),
    ).reset_index()
    z["adverse_first"] = z.resolved_events - z.favorable_first
    z["favorable_first_rate_resolved"] = z.favorable_first / z.resolved_events
    return z

def run(root: Path) -> dict:
    a = _load(root)
    required = {"event_key","symbol","trade_date","direction","event_type","event_family",
                "decision_timestamp_et","first_passage","resolved","subsequent_mfe_pct",
                "subsequent_mae_pct","minutes_to_first_passage"}
    missing = sorted(required - set(a.columns))
    if missing:
        raise RuntimeError(f"missing E3-B3 columns: {missing}")
    if len(a) != EXPECTED_ROWS:
        raise RuntimeError(f"E3-B3 row reconciliation failed: {len(a)} != {EXPECTED_ROWS}")
    directions = set(a.direction.astype(str).str.upper().dropna().unique())
    if directions != VALID_DIRECTIONS:
        raise RuntimeError(f"direction encoding integrity failed: {sorted(directions)}")

    a["trade_date"] = pd.to_datetime(a.trade_date)
    a["month"] = a.trade_date.dt.to_period("M").astype(str)
    a["direction"] = a.direction.astype(str).str.upper()
    same_minute = int((a.first_passage == "SAME_MINUTE").sum())
    unresolved = int((a.first_passage == "UNRESOLVED").sum())
    resolved_directional = a.first_passage.isin(["FAVORABLE_FIRST","ADVERSE_FIRST"])
    resolved_n = int(resolved_directional.sum())

    out = root / "research_outputs/pmpd/edge/e3_batch4"
    out.mkdir(parents=True, exist_ok=True)

    tables = {
        "event_type_overall.csv": _rate_table(a, ["event_family","event_type"]),
        "event_type_by_month.csv": _rate_table(a, ["event_family","event_type","month"]),
        "event_type_by_direction.csv": _rate_table(a, ["event_family","event_type","direction"]),
        "event_type_by_symbol.csv": _rate_table(a, ["event_family","event_type","symbol"]),
    }
    for name, df in tables.items():
        df.to_csv(out/name, index=False)

    per_symbol = a.groupby("symbol").agg(events=("event_key","size"), unique_trades=("event_key","nunique")).reset_index()
    per_symbol["event_share"] = per_symbol.events / len(a)
    per_symbol = per_symbol.sort_values("events", ascending=False)
    per_symbol.to_csv(out/"symbol_concentration.csv", index=False)

    per_trade = a.groupby("event_key").size().rename("events").reset_index()
    per_trade.to_csv(out/"trade_event_concentration.csv", index=False)

    overall = tables["event_type_overall.csv"]
    monthly = tables["event_type_by_month.csv"]
    directional = tables["event_type_by_direction.csv"]
    symboltab = tables["event_type_by_symbol.csv"]

    concentration = {
        "largest_symbol_event_share": float(per_symbol.event_share.max()),
        "top5_symbol_event_share": float(per_symbol.head(5).event_share.sum()),
        "median_events_per_trade": float(per_trade.events.median()),
        "p95_events_per_trade": float(per_trade.events.quantile(.95)),
        "max_events_per_trade": int(per_trade.events.max()),
    }

    robustness = []
    for _, r in overall.iterrows():
        fam, typ = r.event_family, r.event_type
        base = float(r.favorable_first_rate_resolved)
        m = monthly[(monthly.event_family==fam)&(monthly.event_type==typ)&(monthly.resolved_events>=30)]
        d = directional[(directional.event_family==fam)&(directional.event_type==typ)&(directional.resolved_events>=30)]
        s = symboltab[(symboltab.event_family==fam)&(symboltab.event_type==typ)&(symboltab.resolved_events>=30)]
        robustness.append({
            "event_family": fam, "event_type": typ, "overall_rate": base,
            "resolved_events": int(r.resolved_events), "unique_trades": int(r.unique_trades),
            "eligible_month_cells": int(len(m)), "month_rate_min": float(m.favorable_first_rate_resolved.min()) if len(m) else np.nan,
            "month_rate_max": float(m.favorable_first_rate_resolved.max()) if len(m) else np.nan,
            "eligible_direction_cells": int(len(d)), "direction_rate_min": float(d.favorable_first_rate_resolved.min()) if len(d) else np.nan,
            "direction_rate_max": float(d.favorable_first_rate_resolved.max()) if len(d) else np.nan,
            "eligible_symbol_cells": int(len(s)), "symbol_rate_p10": float(s.favorable_first_rate_resolved.quantile(.10)) if len(s) else np.nan,
            "symbol_rate_p90": float(s.favorable_first_rate_resolved.quantile(.90)) if len(s) else np.nan,
        })
    robustness_df = pd.DataFrame(robustness)
    robustness_df.to_csv(out/"robustness_envelope.csv", index=False)

    summary = {
        "step":"PMPD-EDGE-E3-B4","protocol":PROTOCOL,
        "purpose":"Pre-specified robustness and concentration audit of E3-B3 Trade Health associations.",
        "integrity":{"association_rows":int(len(a)),"expected_rows":EXPECTED_ROWS,"row_reconciliation_pass":True,
                     "symbols":int(a.symbol.nunique()),"unique_trades":int(a.event_key.nunique()),
                     "direction_values":sorted(directions),"direction_encoding_pass":True,
                     "same_minute":same_minute,"unresolved":unresolved,"resolved_directional":resolved_n},
        "concentration":concentration,
        "audit_dimensions":["month","direction","symbol","events_per_trade"],
        "cell_reporting_floor":30,
        "guardrails":{"research_only":True,"2026_development_evidence":True,"v4_modified":False,"v5_modified":False,
                      "production_rule_authorized":False,"trade_health_score_fit":False,"threshold_search_performed":False,
                      "event_taxonomy_retuned":False,"signal_quality_separate":True},
        "next_batch_if_integrity_passes":"E3-B5 synthesis/replication-design freeze based on E3-B3/B4 evidence; no production promotion."
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2,default=str))
    outputs=[str((out/n).relative_to(root)) for n in list(tables)+["symbol_concentration.csv","trade_event_concentration.csv","robustness_envelope.csv","summary.json"]]
    print("PMPD_EDGE_E3_B4_SUMMARY="+json.dumps(summary,sort_keys=True,default=str))
    return {"status":"PASS","protocol":PROTOCOL,"output_paths":outputs,"research_only":True,
            "v4_modified":False,"v5_modified":False,"production_rule_authorized":False}
