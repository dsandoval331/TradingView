from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

GEOM_ROOT = Path("data/second1m_alt_entry_research_v1/ae2_session_level_geometry_v1")
TIMING_ROOT = Path("data/second1m_alt_entry_research_v1/ae2_preferred_level_timing_v1")
GEOM = GEOM_ROOT / "a37_session_level_geometry_events_v1.parquet"
TIMING = TIMING_ROOT / "a38_preferred_level_timing_events_v1.parquet"
THRESH = GEOM_ROOT / "a37_geometry_discovery_quintile_thresholds_v1.csv"
OUT = TIMING_ROOT / "a38_vs_a37_independence_audit_v1.csv"
BINARY = {"FAVORABLE_FIRST","ADVERSE_FIRST"}

KEYS = ["symbol","trade_date","direction"]

def stats(x):
    x=x[x["outcome"].isin(BINARY)]
    n=len(x); fav=int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n, (100.0*fav/n if n else np.nan)

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
    g=pd.read_parquet(GEOM)
    t=pd.read_parquet(TIMING)
    for d in (g,t):
        d["trade_date"]=pd.to_datetime(d["trade_date"])

    # Use richer event key when shared by both artifacts.
    keys=[k for k in ["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
          if k in g.columns and k in t.columns]
    if len(keys) < 3:
        keys=KEYS

    needed_g=keys+[
        "mean_pairwise_spacing_pct","directional_level_order_inner_to_outer",
        "pm_pd_spacing_pct","c2_beyond_outermost_pct"
    ]
    x=t.merge(g[needed_g].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    x=x[x["outcome"].isin(BINARY)].copy()
    qm=qmaps()

    # A38 states
    x["A38_P_PM_REMAINS"]=x["c1_levels_cleared_n"].eq(2)&x["c1_cleared_pattern"].eq("AH+PD")
    x["A38_N_PD_REMAINS"]=x["c1_levels_cleared_n"].eq(2)&x["c1_cleared_pattern"].eq("PM+AH")

    # A37 survivors
    x["A37_P_COMPACT_Q2"]=qmask(x,"mean_pairwise_spacing_pct","Q2",qm)
    x["A37_P_ORDER"]=x["directional_level_order_inner_to_outer"].astype(str).eq("PD>AH>PM")
    x["A37_N_PM_PD_Q4"]=qmask(x,"pm_pd_spacing_pct","Q4",qm)
    x["A37_N_OUTER_Q4"]=qmask(x,"c2_beyond_outermost_pct","Q4",qm)

    a38=["A38_P_PM_REMAINS","A38_N_PD_REMAINS"]
    a37=["A37_P_COMPACT_Q2","A37_P_ORDER","A37_N_PM_PD_Q4","A37_N_OUTER_Q4"]

    rows=[]
    for period in ["DISCOVERY","VALIDATION"]:
        p=x[x["research_period"].eq(period)]
        for target in a38:
            for cond in a37:
                mt=p[target]; mc=p[cond]
                inter=int((mt&mc).sum()); union=int((mt|mc).sum())
                tn=int(mt.sum()); cn=int(mc.sum())
                # Target effect when A37 condition absent/present.
                for state,base_mask in [("A37_ABSENT",~mc),("A37_PRESENT",mc)]:
                    base=p[base_mask]; hit=p[base_mask & mt]
                    bn,br=stats(base); hn,hr=stats(hit)
                    rows.append({
                        "research_period":period,"a38_target":target,"a37_condition":cond,
                        "condition_state":state,
                        "a38_n":tn,"a37_n":cn,"intersection_n":inter,
                        "jaccard":inter/union if union else np.nan,
                        "conditional_baseline_n":bn,"conditional_baseline_ff_pct":br,
                        "target_n":hn,"target_ff_pct":hr,
                        "incremental_lift_pp":hr-br if hn else np.nan
                    })

    out=pd.DataFrame(rows)
    out.to_csv(OUT,index=False)

    print("="*120)
    print("A38.4 - A38 vs A37 INDEPENDENCE / REDUNDANCY AUDIT")
    print("="*120)
    print("\nVALIDATION OVERLAP + TARGET EFFECT WHEN A37 FACTOR IS ABSENT")
    print("-"*120)
    z=out[(out["research_period"].eq("VALIDATION"))&(out["condition_state"].eq("A37_ABSENT"))]
    cols=["a38_target","a37_condition","a38_n","a37_n","intersection_n","jaccard",
          "conditional_baseline_n","conditional_baseline_ff_pct","target_n","target_ff_pct","incremental_lift_pp"]
    print(z[cols].to_string(index=False,float_format=lambda v:f"{v:.2f}"))

    print("\nDISCOVERY OVERLAP + TARGET EFFECT WHEN A37 FACTOR IS ABSENT")
    print("-"*120)
    z=out[(out["research_period"].eq("DISCOVERY"))&(out["condition_state"].eq("A37_ABSENT"))]
    print(z[cols].to_string(index=False,float_format=lambda v:f"{v:.2f}"))

    print("\nVALIDATION TARGET EFFECT WHEN A37 FACTOR IS PRESENT (target N >= 10)")
    print("-"*120)
    z=out[(out["research_period"].eq("VALIDATION"))&
          (out["condition_state"].eq("A37_PRESENT"))&
          (out["target_n"].ge(10))]
    cols2=["a38_target","a37_condition","target_n","target_ff_pct",
           "conditional_baseline_n","conditional_baseline_ff_pct","incremental_lift_pp"]
    print(z[cols2].to_string(index=False,float_format=lambda v:f"{v:.2f}") if len(z) else "NONE")

    print(f"\nFull output: {OUT}")
    print("RESULT: A38/A37 INDEPENDENCE AUDIT COMPLETE")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__=="__main__":
    main()
