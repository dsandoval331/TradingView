from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
PRED=ROOT/"ae2_c2_predictors_v1"/"ae2_c2_predictor_features_v1.parquet"
SESS=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
GEO=ROOT/"ae2_session_level_geometry_v1"/"a37_session_level_geometry_events_v1.parquet"
OUTDIR=ROOT/"ae2_c1_c2_transition_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a39_vwap_q3_exact_a37_independence_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}

def stats(x):
    n=len(x); f=int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n,100*f/n if n else np.nan

def ileft(v): return v.left if hasattr(v,"left") else float("-inf")

def main():
    p=pd.read_parquet(PRED); s=pd.read_parquet(SESS); g=pd.read_parquet(GEO)
    for d in (p,s,g):
        if "trade_date" in d.columns: d["trade_date"]=pd.to_datetime(d["trade_date"])

    preferred=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    keys=[k for k in preferred if k in p.columns and k in s.columns and k in g.columns]
    print("="*120)
    print("A39.6 V1.1 - EXACT A37 GEOMETRY INDEPENDENCE AUDIT")
    print("="*120)
    print(f"A37 authoritative source: {GEO}")
    print(f"Join keys: {keys}")

    needg=["pm_pd_spacing_pct","mean_pairwise_spacing_pct","directional_level_order_inner_to_outer"]
    missing=[c for c in needg if c not in g.columns]
    if missing: raise KeyError(f"A37 source missing {missing}")

    ss=s[keys+["session_level_clear_state","market_prior_5d_consensus","research_period"]].drop_duplicates(keys)
    gg=g[keys+needg].drop_duplicates(keys)
    pp=p.drop(columns=[c for c in ["session_level_clear_state","market_prior_5d_consensus","research_period"]+needg if c in p.columns],errors="ignore")
    x=pp.merge(ss,on=keys,how="left",validate="one_to_one").merge(gg,on=keys,how="left",validate="one_to_one")

    if len(x)!=len(p): raise RuntimeError("Join row parity failed.")
    x=x[x["outcome"].isin(BINARY)&x["session_level_clear_state"].eq("ALL_3_CLEARED")&
        x["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")].copy()
    print(f"Historical Preferred binary events: {len(x):,}")

    # A39 frozen upstream Q3
    b="vwap_distance_change_pp__bucket"
    cats=sorted(x[b].dropna().unique(),key=ileft)
    rank={c:i+1 for i,c in enumerate(cats)}
    x["A39_Q3"]=x[b].map(rank).astype("Int64").eq(3)

    # Exact A37 discovery-only quintile thresholds, consistent with original A37 procedure.
    disc=x[x["research_period"].eq("DISCOVERY")]
    for f,name,q in [
        ("mean_pairwise_spacing_pct","A37_COMPACT_Q2",2),
        ("pm_pd_spacing_pct","A37_PM_PD_Q4",4),
    ]:
        _,edges=pd.qcut(disc[f],5,retbins=True,duplicates="drop")
        edges=edges.astype(float); edges[0]=-np.inf; edges[-1]=np.inf
        x[name]=pd.cut(x[f],bins=edges,labels=range(1,len(edges)),include_lowest=True).astype("Int64").eq(q)

    # Use exact authoritative ordering label; print values before selecting.
    print("\nA37 ordering values:")
    print(x["directional_level_order_inner_to_outer"].value_counts(dropna=False).to_string())
    order_strings=x["directional_level_order_inner_to_outer"].astype(str)
    target_candidates=["PD>AH>PM","PD > AH > PM","PD|AH|PM","PD_AH_PM"]
    target=next((t for t in target_candidates if (order_strings==t).any()),None)
    if target is None:
        raise RuntimeError("Could not match authoritative PD>AH>PM order label; values printed above.")
    x["A37_ORDER_PD_AH_PM"]=order_strings.eq(target)
    print(f"Matched PD>AH>PM label: {target}")

    # Parity counts against frozen A37 record before interpreting independence.
    print("\nPARITY COUNTS")
    for period in ["DISCOVERY","VALIDATION"]:
        z=x[x["research_period"].eq(period)]
        print(period,
              "COMPACT_Q2=",int(z["A37_COMPACT_Q2"].sum()),
              "PM_PD_Q4=",int(z["A37_PM_PD_Q4"].sum()),
              "ORDER_PD_AH_PM=",int(z["A37_ORDER_PD_AH_PM"].sum()))

    rows=[]
    for period in ["DISCOVERY","VALIDATION"]:
        z=x[x["research_period"].eq(period)]
        bn,br=stats(z); h=z[z["A39_Q3"]]; n,r=stats(h)
        rows.append([period,"POOLED","ALL",n,r,bn,br,r-br])
        for f in ["A37_COMPACT_Q2","A37_PM_PD_Q4","A37_ORDER_PD_AH_PM"]:
            base=z[~z[f]]; b_n,b_r=stats(base); hit=base[base["A39_Q3"]]; h_n,h_r=stats(hit)
            rows.append([period,"A37_ABSENT",f,h_n,h_r,b_n,b_r,h_r-b_r if h_n else np.nan])

    out=pd.DataFrame(rows,columns=["research_period","split_type","split_value","candidate_n","candidate_ff_pct",
                                   "conditional_baseline_n","conditional_baseline_ff_pct","incremental_lift_pp"])
    out.to_csv(OUT,index=False)
    print("\nINDEPENDENCE RESULTS")
    print("-"*120)
    print(out.to_string(index=False,float_format=lambda v:f"{v:.2f}"))
    print(f"\nOutput: {OUT}")
    print("RESULT: EXACT A37 INDEPENDENCE AUDIT COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__=="__main__": main()
