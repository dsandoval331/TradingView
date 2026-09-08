from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("data/second1m_alt_entry_research_v1")
PRED = ROOT/"ae2_c2_predictors_v1"/"ae2_c2_predictor_features_v1.parquet"
SESS = ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
OUTDIR = ROOT/"ae2_c1_c2_transition_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR/"a39_vwap_q3_prior_survivor_independence_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}

def stats(x):
    n=len(x); f=int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n,100*f/n if n else np.nan

def ileft(v):
    return v.left if hasattr(v,"left") else float("-inf")

def main():
    p=pd.read_parquet(PRED); s=pd.read_parquet(SESS)
    for d in (p,s): d["trade_date"]=pd.to_datetime(d["trade_date"])
    keys=[k for k in ["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
          if k in p.columns and k in s.columns]

    need=[
        "session_level_clear_state","market_prior_5d_consensus","research_period",
        "pm_directional_level","ah_directional_level","pd_directional_level",
    ]
    miss=[c for c in need if c not in s.columns]
    if miss: raise KeyError(f"Session source missing: {miss}")

    ss=s[keys+need].drop_duplicates(keys)
    pp=p.drop(columns=[c for c in need if c in p.columns],errors="ignore")
    x=pp.merge(ss,on=keys,how="left",validate="one_to_one")
    if len(x)!=len(p): raise RuntimeError("Join row parity failed.")

    x=x[
        x["outcome"].isin(BINARY)
        & x["session_level_clear_state"].eq("ALL_3_CLEARED")
        & x["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")
    ].copy()

    # A39 Q3
    b="vwap_distance_change_pp__bucket"
    cats=sorted(x[b].dropna().unique(),key=ileft)
    rank={c:i+1 for i,c in enumerate(cats)}
    x["A39_Q3"]=x[b].map(rank).astype("Int64").eq(3)

    # A38 timing states, mechanically reconstructed from C1 close and frozen directional levels.
    sign=np.where(x["direction"].eq("BULL"),1.0,-1.0)
    for tag,col in [("PM","pm_directional_level"),("AH","ah_directional_level"),("PD","pd_directional_level")]:
        x[f"C1_{tag}_CLEARED"]=(sign*(x["c1_close"]-x[col]))>0
    x["A38_PM_REMAINS"]=(~x["C1_PM_CLEARED"]) & x["C1_AH_CLEARED"] & x["C1_PD_CLEARED"]
    x["A38_PD_REMAINS"]=x["C1_PM_CLEARED"] & x["C1_AH_CLEARED"] & (~x["C1_PD_CLEARED"])

    # A37 geometry frozen quintiles reconstructed from raw frozen levels/entry.
    vals=x[["pm_directional_level","ah_directional_level","pd_directional_level"]]
    x["mean_pairwise_spacing_pct"]=(
        (vals["pm_directional_level"]-vals["ah_directional_level"]).abs()
        +(vals["pm_directional_level"]-vals["pd_directional_level"]).abs()
        +(vals["ah_directional_level"]-vals["pd_directional_level"]).abs()
    )/3/x["entry_price"]*100
    x["pm_pd_spacing_pct"]=(vals["pm_directional_level"]-vals["pd_directional_level"]).abs()/x["entry_price"]*100

    # Freeze quintile cutpoints from DISCOVERY only, then apply to both periods.
    disc=x[x["research_period"].eq("DISCOVERY")]
    for f,name,q in [
        ("mean_pairwise_spacing_pct","A37_COMPACT_Q2",2),
        ("pm_pd_spacing_pct","A37_PM_PD_Q4",4),
    ]:
        edges=np.quantile(disc[f].dropna(),[0,.2,.4,.6,.8,1])
        edges[0]=-np.inf; edges[-1]=np.inf
        x[name]=(pd.cut(x[f],bins=edges,labels=[1,2,3,4,5],include_lowest=True).astype("Int64")==q)

    # A37 order PD>AH>PM is directional favorable ordering.
    dn=pd.DataFrame({
        "PM":sign*(x["pm_directional_level"]-x["entry_price"]),
        "AH":sign*(x["ah_directional_level"]-x["entry_price"]),
        "PD":sign*(x["pd_directional_level"]-x["entry_price"]),
    },index=x.index)
    # Equivalent raw ordering in favorable-normalized coordinate.
    x["A37_ORDER_PD_AH_PM"]=(dn["PD"]>dn["AH"]) & (dn["AH"]>dn["PM"])

    survivors=[
        "A38_PM_REMAINS","A38_PD_REMAINS",
        "A37_COMPACT_Q2","A37_PM_PD_Q4","A37_ORDER_PD_AH_PM",
    ]
    rows=[]
    for period in ["DISCOVERY","VALIDATION"]:
        z=x[x["research_period"].eq(period)]
        bn,br=stats(z)
        q=z[z["A39_Q3"]]; qn,qr=stats(q)
        rows.append([period,"POOLED","ALL",qn,qr,bn,br,qr-br])
        for f in survivors:
            # Key independence test: A39 effect when prior survivor is ABSENT.
            base=z[~z[f]]
            n0,r0=stats(base); hit=base[base["A39_Q3"]]; n,r=stats(hit)
            rows.append([period,"SURVIVOR_ABSENT",f,n,r,n0,r0,r-r0 if n else np.nan])

            # Descriptive overlap only.
            base2=z[z[f]]
            n1,r1=stats(base2); hit2=base2[base2["A39_Q3"]]; n2,r2=stats(hit2)
            rows.append([period,"SURVIVOR_PRESENT",f,n2,r2,n1,r1,r2-r1 if n2 else np.nan])

    out=pd.DataFrame(rows,columns=[
        "research_period","split_type","split_value","candidate_n","candidate_ff_pct",
        "conditional_baseline_n","conditional_baseline_ff_pct","incremental_lift_pp"
    ])
    out.to_csv(OUT,index=False)

    print("="*120)
    print("A39.6 - VWAP Q3 vs A37/A38 SURVIVOR INDEPENDENCE AUDIT")
    print("="*120)
    print(f"Historical Preferred binary events: {len(x):,}")
    print("Primary interpretation = SURVIVOR_ABSENT rows. PRESENT rows are descriptive overlap only.")
    print(out.to_string(index=False,float_format=lambda v:f"{v:.2f}"))
    print(f"\nOutput: {OUT}")
    print("RESULT: A39 PRIOR-SURVIVOR INDEPENDENCE AUDIT COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__=="__main__":
    main()
