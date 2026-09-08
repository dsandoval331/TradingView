from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

GEOM_ROOT = Path("data/second1m_alt_entry_research_v1/ae2_session_level_geometry_v1")
TIMING_ROOT = Path("data/second1m_alt_entry_research_v1/ae2_preferred_level_timing_v1")
GEOM = GEOM_ROOT / "a37_session_level_geometry_events_v1.parquet"
TIMING = TIMING_ROOT / "a38_preferred_level_timing_events_v1.parquet"
THRESH = GEOM_ROOT / "a37_geometry_discovery_quintile_thresholds_v1.csv"
OUT = TIMING_ROOT / "a38_survivor_family_overlap_v1.csv"
BINARY = {"FAVORABLE_FIRST","ADVERSE_FIRST"}

def stats(x):
    x=x[x["outcome"].isin(BINARY)]
    n=len(x); fav=int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n, 100.0*fav/n if n else np.nan

def qmaps():
    t=pd.read_csv(THRESH); out={}
    for metric,g in t.groupby("metric"):
        m=dict(zip(g["cutpoint"],g["value"]))
        if all(k in m for k in ("q20","q40","q60","q80")):
            out[metric]=[-np.inf,m["q20"],m["q40"],m["q60"],m["q80"],np.inf]
    return out

def qmask(e, feature, q, qm):
    return pd.cut(pd.to_numeric(e[feature],errors="coerce"),
                  qm[feature],labels=["Q1","Q2","Q3","Q4","Q5"],
                  include_lowest=True).astype("object").eq(q)

def main():
    g=pd.read_parquet(GEOM); t=pd.read_parquet(TIMING)
    for d in (g,t):
        d["trade_date"]=pd.to_datetime(d["trade_date"])
    keys=[k for k in ["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
          if k in g.columns and k in t.columns]
    if len(keys)<3: keys=["symbol","trade_date","direction"]

    need=keys+["mean_pairwise_spacing_pct","directional_level_order_inner_to_outer",
               "pm_pd_spacing_pct","c2_beyond_outermost_pct"]
    x=t.merge(g[need].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    x=x[x["outcome"].isin(BINARY)].copy()
    qm=qmaps()

    x["P_TIMING_PM_REMAINS"]=x["c1_levels_cleared_n"].eq(2)&x["c1_cleared_pattern"].eq("AH+PD")
    x["N_TIMING_PD_REMAINS"]=x["c1_levels_cleared_n"].eq(2)&x["c1_cleared_pattern"].eq("PM+AH")
    x["P_GEOM_COMPACT_Q2"]=qmask(x,"mean_pairwise_spacing_pct","Q2",qm)
    x["P_GEOM_ORDER"]=x["directional_level_order_inner_to_outer"].astype(str).eq("PD>AH>PM")
    x["N_GEOM_PM_PD_Q4"]=qmask(x,"pm_pd_spacing_pct","Q4",qm)
    x["N_GEOM_OUTER_Q4"]=qmask(x,"c2_beyond_outermost_pct","Q4",qm)

    pos=["P_TIMING_PM_REMAINS","P_GEOM_COMPACT_Q2","P_GEOM_ORDER"]
    neg=["N_TIMING_PD_REMAINS","N_GEOM_PM_PD_Q4","N_GEOM_OUTER_Q4"]

    rows=[]
    for period in ["DISCOVERY","VALIDATION"]:
        p=x[x["research_period"].eq(period)]
        bn,br=stats(p)
        for family, cols in [("POSITIVE",pos),("NEGATIVE",neg)]:
            count=p[cols].sum(axis=1)
            for k in range(0,4):
                z=p[count.eq(k)]
                n,r=stats(z)
                rows.append({"research_period":period,"family":family,"state":f"EXACT_{k}",
                             "binary_n":n,"ff_pct":r,"baseline_ff_pct":br,
                             "lift_pp":r-br if n else np.nan})
            z=p[count.ge(1)]; n,r=stats(z)
            rows.append({"research_period":period,"family":family,"state":"ANY",
                         "binary_n":n,"ff_pct":r,"baseline_ff_pct":br,
                         "lift_pp":r-br if n else np.nan})
            z=p[count.ge(2)]; n,r=stats(z)
            rows.append({"research_period":period,"family":family,"state":"TWO_PLUS",
                         "binary_n":n,"ff_pct":r,"baseline_ff_pct":br,
                         "lift_pp":r-br if n else np.nan})

    out=pd.DataFrame(rows)
    out.to_csv(OUT,index=False)

    print("="*112)
    print("A38.5 - SURVIVING GEOMETRY + TIMING FAMILY OVERLAP SUMMARY")
    print("="*112)
    print(out.to_string(index=False,float_format=lambda v:f"{v:.2f}"))
    print("\nIMPORTANT: descriptive consolidation only; not a new model or vote-count rule.")
    print(f"Full output: {OUT}")
    print("RESULT: SURVIVOR FAMILY SUMMARY COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__=="__main__":
    main()
