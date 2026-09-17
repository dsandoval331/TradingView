from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
from research_runner.jobs import pmpd_edge_e2_batch2 as e2

PROTOCOL = "PMPD_EDGE_E3_TRADE_HEALTH_PROTOCOL_V1"
FAV = 0.005
ADV = 0.005


def _load_events(root: Path) -> pd.DataFrame:
    shard_dir = root / "research_outputs/pmpd/edge/e3_batch2_r2"
    parts = sorted(shard_dir.glob("trade_health_events_part_*.parquet"))
    if not parts:
        legacy = root / "research_outputs/pmpd/edge/e3_batch2/trade_health_events.parquet"
        if legacy.exists():
            return pd.read_parquet(legacy)
        raise FileNotFoundError("E3-B2-R2 Trade Health event shards not found")
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)


def _future_outcome(minutes: pd.DataFrame, trade_date, t: pd.Timestamp, direction: str, price: float) -> dict:
    sign = 1 if direction == "BULL" else -1
    q = minutes[(minutes.trade_date == trade_date) & (minutes.timestamp_et > t)].copy()
    if q.empty or not np.isfinite(price) or price <= 0:
        return {"resolved": False, "first_passage": "UNRESOLVED", "minutes_to_first_passage": np.nan,
                "subsequent_mfe_pct": np.nan, "subsequent_mae_pct": np.nan}
    q["fav_hi"] = np.where(sign == 1, q.high.astype(float) / price - 1, price / q.low.astype(float) - 1)
    q["adv_hi"] = np.where(sign == 1, 1 - q.low.astype(float) / price, q.high.astype(float) / price - 1)
    fav_idx = q.index[q.fav_hi >= FAV]
    adv_idx = q.index[q.adv_hi >= ADV]
    ft = pd.Timestamp(q.loc[fav_idx[0], "timestamp_et"]) if len(fav_idx) else None
    at = pd.Timestamp(q.loc[adv_idx[0], "timestamp_et"]) if len(adv_idx) else None
    if ft is not None and (at is None or ft < at): first, hit = "FAVORABLE_FIRST", ft
    elif at is not None and (ft is None or at < ft): first, hit = "ADVERSE_FIRST", at
    elif ft is not None and at is not None: first, hit = "SAME_MINUTE", ft
    else: first, hit = "UNRESOLVED", None
    return {"resolved": first != "UNRESOLVED", "first_passage": first,
            "minutes_to_first_passage": float((hit - t).total_seconds()/60) if hit is not None else np.nan,
            "subsequent_mfe_pct": float(q.fav_hi.max()), "subsequent_mae_pct": float(q.adv_hi.max())}


def run(root: Path) -> dict:
    proto_p = root / "research_outputs/pmpd/edge/e3_batch1/trade_health_protocol.json"
    cache = root / "data/second1m_alt_entry_cache_v1/partitions"
    if not proto_p.exists(): raise FileNotFoundError(proto_p)
    proto = json.loads(proto_p.read_text())
    if proto.get("protocol") != PROTOCOL: raise RuntimeError("E3 protocol mismatch")
    ev = _load_events(root)
    required = {"event_key","symbol","trade_date","direction","event_type","event_family","decision_timestamp_et","price_at_decision"}
    missing_cols = sorted(required - set(ev.columns))
    if missing_cols: raise RuntimeError(f"missing E3-B2 columns: {missing_cols}")
    rows=[]; missing=[]; errors=[]
    for n,sym in enumerate(sorted(ev.symbol.astype(str).unique()),1):
        print(f"[{n}/{ev.symbol.nunique()}] E3_B3_ASSOC {sym}")
        d=e2._load_cache(cache,sym)
        if d is None: missing.append(sym); continue
        try: minutes,_,_=e2._prepare_symbol(d)
        except Exception as exc: errors.append({"symbol":sym,"error":repr(exc)}); continue
        for _,r in ev[ev.symbol.astype(str)==sym].iterrows():
            t=pd.Timestamp(r.decision_timestamp_et)
            out=_future_outcome(minutes,r.trade_date,t,str(r.direction).upper(),float(r.price_at_decision))
            rows.append({**r.to_dict(),**out})
    assoc=pd.DataFrame(rows)
    if len(assoc):
        assoc=assoc.sort_values(["symbol","trade_date","decision_timestamp_et","event_type"])
    outdir=root/"research_outputs/pmpd/edge/e3_batch3"; outdir.mkdir(parents=True,exist_ok=True)
    # Shard by symbol groups to remain below governed artifact-size limits.
    syms=sorted(assoc.symbol.astype(str).unique()) if len(assoc) else []
    shard_paths=[]
    for i,group in enumerate(np.array_split(syms,16)):
        if not len(group): continue
        p=outdir/f"trade_health_associations_part_{i:02d}.parquet"
        assoc[assoc.symbol.astype(str).isin(list(group))].to_parquet(p,index=False)
        shard_paths.append(p)
    valid=assoc[assoc.first_passage.isin(["FAVORABLE_FIRST","ADVERSE_FIRST"])] if len(assoc) else assoc
    def summarize(df):
        if df.empty:return pd.DataFrame()
        g=df.groupby(["event_family","event_type"],dropna=False)
        z=g.agg(events=("event_key","size"),unique_trades=("event_key","nunique"),symbols=("symbol","nunique"),resolved=("resolved","sum"),median_subsequent_mfe_pct=("subsequent_mfe_pct","median"),median_subsequent_mae_pct=("subsequent_mae_pct","median"),median_minutes_to_first_passage=("minutes_to_first_passage","median")).reset_index()
        fav=(df[df.first_passage=="FAVORABLE_FIRST"].groupby(["event_family","event_type"]).size().rename("favorable_first").reset_index())
        adv=(df[df.first_passage=="ADVERSE_FIRST"].groupby(["event_family","event_type"]).size().rename("adverse_first").reset_index())
        z=z.merge(fav,how="left").merge(adv,how="left").fillna({"favorable_first":0,"adverse_first":0})
        den=z.favorable_first+z.adverse_first
        z["favorable_first_rate_resolved"]=np.where(den>0,z.favorable_first/den,np.nan)
        return z
    summary_table=summarize(assoc)
    summary_table.to_csv(outdir/"event_association_summary.csv",index=False)
    # Pre-specified supportive/warning grouping from frozen B1 protocol; no fitting or ranking.
    supportive=set(proto["trade_health_role"]["supportive_events"]); warning=set(proto["trade_health_role"]["warning_events"])
    assoc["hypothesis_role"]=np.where(assoc.event_type.isin(supportive),"SUPPORTIVE",np.where(assoc.event_type.isin(warning),"WARNING","DESCRIPTIVE"))
    role=summarize(assoc.assign(event_family=assoc.hypothesis_role,event_type=assoc.hypothesis_role))
    role.to_csv(outdir/"hypothesis_role_summary.csv",index=False)
    summary={"step":"PMPD-EDGE-E3-B3","protocol":PROTOCOL,"purpose":"Pre-specified association of causal Trade Health events with subsequent path/outcomes from each event decision timestamp.","source_event_rows":int(len(ev)),"association_rows":int(len(assoc)),"unique_trades":int(assoc.event_key.nunique()) if len(assoc) else 0,"symbols":int(assoc.symbol.nunique()) if len(assoc) else 0,"missing_cache_symbols":missing,"symbol_errors":errors,"outcome_definition":{"favorable_first_pct":FAV,"adverse_first_pct":ADV,"anchor":"event decision_timestamp_et / price_at_decision","same_minute":"reported separately, excluded from directional first-passage rate"},"guardrails":{"research_only":True,"2026_development_evidence":True,"v4_modified":False,"v5_modified":False,"production_rule_authorized":False,"trade_health_score_fit":False,"threshold_search_performed":False,"event_taxonomy_retuned":False,"signal_quality_separate":True},"next_batch_if_integrity_passes":"E3-B4 robustness and concentration audit of pre-specified E3-B3 associations; no threshold mining or score fitting."}
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2,default=str))
    outputs=[str(p.relative_to(root)) for p in shard_paths]+[str((outdir/"event_association_summary.csv").relative_to(root)),str((outdir/"hypothesis_role_summary.csv").relative_to(root)),str((outdir/"summary.json").relative_to(root))]
    print("PMPD_EDGE_E3_B3_SUMMARY="+json.dumps(summary,sort_keys=True,default=str))
    return {"status":"PASS","protocol":PROTOCOL,"output_paths":outputs,"research_only":True,"v4_modified":False,"v5_modified":False,"production_rule_authorized":False}
