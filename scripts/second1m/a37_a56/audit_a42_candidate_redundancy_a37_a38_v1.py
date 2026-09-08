from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
BASE=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
FEAT=ROOT/"ae2_opening_location_geometry_v1"/"a42_opening_location_features_v1.parquet"
THR=ROOT/"ae2_opening_location_geometry_v1"/"a42_discovery_quintile_thresholds_v1.csv"
OUTDIR=ROOT/"ae2_opening_location_geometry_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a42_candidate_redundancy_a37_a38_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}

def stats(x):
    n=len(x); f=int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n,100*f/n if n else np.nan

def apply_q(x,col,t):
    r=t[t.feature.eq(col)].iloc[0]
    e=np.array([r[f"edge_{i}"] for i in range(6)],float)
    e[0]=-np.inf; e[-1]=np.inf
    return pd.cut(x[col],e,labels=["Q1","Q2","Q3","Q4","Q5"],include_lowest=True)

def main():
    b=pd.read_parquet(BASE); f=pd.read_parquet(FEAT); t=pd.read_csv(THR)
    for d in (b,f): d["trade_date"]=pd.to_datetime(d["trade_date"])
    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    cols=["a42_open_to_pd_level_dir_pct","a42_priorclose_to_outer_consumed_ratio"]
    x=b.merge(f[keys+cols].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    x=x[x["outcome"].isin(BINARY)&x["session_level_clear_state"].eq("ALL_3_CLEARED")&
        x["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")].copy()

    x["A42_PD_Q5"]=apply_q(x,cols[0],t).eq("Q5")
    x["A42_CONSUMED_Q2"]=apply_q(x,cols[1],t).eq("Q2")

    # Exact A38 timing states from C1 and authoritative directional levels.
    sign=np.where(x["direction"].eq("BULL"),1.0,-1.0)
    for tag,col in [("PM","pm_directional_level"),("AH","ah_directional_level"),("PD","pd_directional_level")]:
        x[f"C1_{tag}_CLEARED"]=(sign*(x["c1_close"]-x[col]))>0
    x["A38_PM_REMAINS"]=(~x.C1_PM_CLEARED)&x.C1_AH_CLEARED&x.C1_PD_CLEARED
    x["A38_PD_REMAINS"]=x.C1_PM_CLEARED&x.C1_AH_CLEARED&(~x.C1_PD_CLEARED)

    # Exact A37 artifact + frozen discovery quintiles.
    geo=ROOT/"ae2_session_level_geometry_v1"/"a37_session_level_geometry_events_v1.parquet"
    g=pd.read_parquet(geo); g["trade_date"]=pd.to_datetime(g["trade_date"])
    gcols=keys+["pm_pd_spacing_pct","mean_pairwise_spacing_pct","directional_level_order_inner_to_outer"]
    x=x.merge(g[gcols].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")

    disc=x[x.research_period.eq("DISCOVERY")]
    for col,name,q in [
        ("mean_pairwise_spacing_pct","A37_COMPACT_Q2",2),
        ("pm_pd_spacing_pct","A37_PM_PD_Q4",4),
    ]:
        _,edges=pd.qcut(disc[col],5,retbins=True,duplicates="drop")
        edges=edges.astype(float); edges[0]=-np.inf; edges[-1]=np.inf
        x[name]=pd.cut(x[col],edges,labels=[1,2,3,4,5],include_lowest=True).astype("Int64").eq(q)
    x["A37_ORDER_PD_AH_PM"]=x["directional_level_order_inner_to_outer"].astype(str).eq("PD>AH>PM")

    prior=["A38_PM_REMAINS","A38_PD_REMAINS","A37_COMPACT_Q2","A37_PM_PD_Q4","A37_ORDER_PD_AH_PM"]
    cands=["A42_PD_Q5","A42_CONSUMED_Q2"]
    rows=[]
    print("="*125)
    print("A42.5 - REDUNDANCY / INDEPENDENCE vs A37-A38")
    print("="*125)

    for cand in cands:
        print(f"\n{cand}")
        for period in ["DISCOVERY","VALIDATION"]:
            z=x[x.research_period.eq(period)]
            cn=int(z[cand].sum())
            print(f"\n{period} candidate N={cn}")
            for p in prior:
                inter=int((z[cand]&z[p]).sum()); union=int((z[cand]|z[p]).sum())
                jac=inter/union if union else np.nan
                base=z[~z[p]]; bn,br=stats(base)
                hit=base[base[cand]]; n,r=stats(hit)
                lift=r-br if n else np.nan
                rows.append([cand,period,p,cn,int(z[p].sum()),inter,jac,n,r,bn,br,lift])
                print(f"  {p:22s} overlap={inter:3d} J={jac:.2f} | when absent: N={n:3d} FF={r:6.2f}% vs {br:6.2f}% lift={lift:+6.2f}pp")

    out=pd.DataFrame(rows,columns=[
        "candidate","research_period","prior_factor","candidate_n","prior_factor_n","intersection_n","jaccard",
        "candidate_when_prior_absent_n","candidate_when_prior_absent_ff_pct",
        "conditional_baseline_n","conditional_baseline_ff_pct","incremental_lift_pp"
    ])
    out.to_csv(OUT,index=False)
    print(f"\nOutput: {OUT}")
    print("RESULT: A42 REDUNDANCY / INDEPENDENCE AUDIT COMPLETE")
    print("No thresholds changed. No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
