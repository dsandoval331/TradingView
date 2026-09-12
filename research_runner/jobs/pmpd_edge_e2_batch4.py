from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

PROTOCOL = "PMPD_EDGE_E2_ACCEPTANCE_PROTOCOL_V1"
STATE = "reclaim_after_failure"
SEED = 9162026
REPS = 10000


def _stats(g: pd.DataFrame) -> dict:
    s = g[f"{STATE}_outcome"].astype(str)
    fav = int((s == "FAVORABLE_FIRST").sum())
    adv = int((s == "ADVERSE_FIRST").sum())
    amb = int((s == "AMBIGUOUS_SAME_BAR").sum())
    unr = int((s == "UNRESOLVED").sum())
    resolved = fav + adv
    return {"events": int(len(g)), "resolved": resolved, "favorable": fav, "adverse": adv,
            "ambiguous": amb, "unresolved": unr, "rate": float(fav/resolved) if resolved else np.nan}


def _rate_ci_symbol_cluster(g: pd.DataFrame) -> tuple[float,float,float]:
    syms = np.array(sorted(g["symbol"].astype(str).unique()))
    z = g[["symbol", f"{STATE}_outcome"]].copy()
    z["fav"] = (z[f"{STATE}_outcome"] == "FAVORABLE_FIRST").astype(int)
    z["adv"] = (z[f"{STATE}_outcome"] == "ADVERSE_FIRST").astype(int)
    c = z.groupby("symbol")[["fav","adv"]].sum().reindex(syms, fill_value=0).to_numpy()
    rng = np.random.default_rng(SEED)
    vals=[]
    for _ in range(REPS):
        idx=rng.integers(0,len(syms),size=len(syms)); f,a=c[idx].sum(axis=0)
        if f+a: vals.append(f/(f+a))
    return tuple(map(float,np.quantile(vals,[.025,.5,.975]))) if vals else (np.nan,np.nan,np.nan)


def run(root: Path) -> dict:
    p=root/"research_outputs"/"pmpd"/"edge"/"e2_batch3"/"state_anchored_outcomes.parquet"
    proto=root/"research_outputs"/"pmpd"/"edge"/"e2_batch1"/"acceptance_protocol.json"
    if not p.exists() or not proto.exists(): raise FileNotFoundError("required governed E2 input missing")
    if json.loads(proto.read_text()).get("protocol") != PROTOCOL: raise RuntimeError("protocol mismatch")
    x=pd.read_parquet(p).copy()
    g=x[x[f"{STATE}_seen"].fillna(False)].copy()
    g["trade_date"]=pd.to_datetime(g["trade_date"])
    g["month"]=g["trade_date"].dt.to_period("M").astype(str)
    g["rvol_context"]=np.where(g["opening_rvol_ge_1_5"].fillna(False),"rvol_ge_1_5","rvol_lt_1_5_or_unavailable")

    overall=_stats(g); lo,med,hi=_rate_ci_symbol_cluster(g); overall.update({"ci95_lower":lo,"bootstrap_median":med,"ci95_upper":hi})
    rows=[]
    for dim in ["month","direction","rvol_context"]:
        for key,h in g.groupby(dim): rows.append({"dimension":dim,"value":str(key),**_stats(h)})
    robustness=pd.DataFrame(rows)

    # Symbol concentration and leave-one-symbol-out rate stability.
    sym=[]
    base_rate=overall["rate"]
    for s,h in g.groupby("symbol"):
        st=_stats(h); sym.append({"symbol":str(s),**st,"event_share":len(h)/len(g)})
    symbols=pd.DataFrame(sym).sort_values("events",ascending=False)
    loo=[]
    for s in sorted(g["symbol"].astype(str).unique()):
        h=g[g["symbol"].astype(str)!=s]; st=_stats(h)
        loo.append({"excluded_symbol":s,"rate":st["rate"],"delta_vs_full":st["rate"]-base_rate,"resolved":st["resolved"]})
    loo=pd.DataFrame(loo)

    # Prespecified RVOL >=1.5 focus only; no threshold search.
    rg=g[g["opening_rvol_ge_1_5"].fillna(False)].copy(); rst=_stats(rg)
    rlo,rmed,rhi=_rate_ci_symbol_cluster(rg); rst.update({"ci95_lower":rlo,"bootstrap_median":rmed,"ci95_upper":rhi})
    rm=robustness[(robustness.dimension=="month")].copy()
    # Month/direction within frozen RVOL context.
    rr=[]
    for dim in ["month","direction"]:
        for key,h in rg.groupby(dim): rr.append({"dimension":dim,"value":str(key),**_stats(h)})
    rr=pd.DataFrame(rr)

    out=root/"research_outputs"/"pmpd"/"edge"/"e2_batch4"; out.mkdir(parents=True,exist_ok=True)
    robustness.to_csv(out/"robustness.csv",index=False); symbols.to_csv(out/"symbol_concentration.csv",index=False); loo.to_csv(out/"leave_one_symbol_out.csv",index=False); rr.to_csv(out/"rvol_ge_1_5_robustness.csv",index=False)
    summary={"step":"PMPD-EDGE-E2-B4","protocol":PROTOCOL,"state":STATE,"purpose":"Focused robustness audit of reclaim-after-failure and the prespecified opening RVOL >=1.5 context; no threshold search.","overall":overall,"rvol_ge_1_5":rst,"months_positive_over_0_5":int(((rm.rate>.5)&(rm.resolved>0)).sum()),"months_total":int((rm.resolved>0).sum()),"top10_event_share":float(symbols.head(10).event_share.sum()),"loo_min_rate":float(loo.rate.min()),"loo_max_rate":float(loo.rate.max()),"guardrails":{"research_only":True,"2026_development_evidence":True,"v4_modified":False,"v5_modified":False,"production_rule_authorized":False,"acceptance_definitions_retuned":False,"rvol_threshold_retuned":False,"new_threshold_search":False,"trade_health_reserved_for_e3":True},"adjudication_rule":"Carry forward only if the reclaim/RVOL pocket is not obviously explained by temporal, directional, or symbol concentration and remains practically interesting after sample-size uncertainty; otherwise close E2 without promotion."}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,default=str))
    return {"status":"PASS","output_paths":[str((out/f).relative_to(root)) for f in ["robustness.csv","symbol_concentration.csv","leave_one_symbol_out.csv","rvol_ge_1_5_robustness.csv","summary.json"]],"research_only":True,"v4_modified":False,"v5_modified":False,"production_rule_authorized":False}
