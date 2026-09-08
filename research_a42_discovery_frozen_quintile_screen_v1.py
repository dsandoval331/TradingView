from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
BASE=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
FEAT=ROOT/"ae2_opening_location_geometry_v1"/"a42_opening_location_features_v1.parquet"
OUTDIR=ROOT/"ae2_opening_location_geometry_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
THRESH=OUTDIR/"a42_discovery_quintile_thresholds_v1.csv"
OUT=OUTDIR/"a42_predeclared_quintile_screen_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}

FEATURES=[
 "a42_open_from_prior_close_dir_pct",
 "a42_open_to_pm_level_dir_pct",
 "a42_open_to_ah_level_dir_pct",
 "a42_open_to_pd_level_dir_pct",
 "a42_open_to_outermost_dir_pct",
 "a42_priorclose_to_outer_consumed_ratio",
]

def stats(x):
    n=len(x); f=int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n,100*f/n if n else np.nan

def main():
    b=pd.read_parquet(BASE); f=pd.read_parquet(FEAT)
    for d in (b,f): d["trade_date"]=pd.to_datetime(d["trade_date"])
    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    x=b.merge(f[keys+FEATURES].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    if len(x)!=len(b): raise RuntimeError("Join parity failed.")

    x=x[x["outcome"].isin(BINARY)&
        x["session_level_clear_state"].eq("ALL_3_CLEARED")&
        x["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")].copy()

    disc=x[x["research_period"].eq("DISCOVERY")]
    thresholds=[]
    for col in FEATURES:
        vals=disc[col].dropna()
        _,edges=pd.qcut(vals,5,retbins=True,duplicates="drop")
        if len(edges)!=6:
            raise RuntimeError(f"{col}: expected 5 quintiles, got {len(edges)-1}")
        thresholds.append({"feature":col,**{f"edge_{i}":float(v) for i,v in enumerate(edges)}})
        bins=edges.astype(float).copy(); bins[0]=-np.inf; bins[-1]=np.inf
        x[col+"__A42Q"]=pd.cut(x[col],bins=bins,labels=["Q1","Q2","Q3","Q4","Q5"],include_lowest=True)

    pd.DataFrame(thresholds).to_csv(THRESH,index=False)

    rows=[]
    print("="*125)
    print("A42.3 - DISCOVERY-FROZEN QUINTILE SCREEN")
    print("="*125)
    print(f"Historical Preferred binary events: {len(x):,}")
    print("Quintile edges are derived from DISCOVERY only and applied unchanged to VALIDATION.")

    for period in ["DISCOVERY","VALIDATION"]:
        z=x[x["research_period"].eq(period)]
        bn,br=stats(z)
        print(f"\n{period} BASELINE N={bn} FF={br:.2f}%")
        for col in FEATURES:
            print(f"\n{col}")
            for q in ["Q1","Q2","Q3","Q4","Q5"]:
                h=z[z[col+"__A42Q"].eq(q)]
                n,r=stats(h); lift=r-br if n else np.nan
                rows.append([period,col,q,n,r,br,lift])
                print(f"  {q}: N={n:3d} FF={r:6.2f}% lift={lift:+6.2f}pp" if n else f"  {q}: N=0")

    out=pd.DataFrame(rows,columns=[
        "research_period","feature","quintile","n","ff_pct","preferred_baseline_ff_pct","lift_pp"
    ])
    out.to_csv(OUT,index=False)

    print("\nREPLICATION CANDIDATES: same lift sign and |lift| >= 3pp in BOTH periods")
    print("-"*125)
    d=out[out.research_period.eq("DISCOVERY")].set_index(["feature","quintile"])
    v=out[out.research_period.eq("VALIDATION")].set_index(["feature","quintile"])
    found=0
    for idx in d.index.intersection(v.index):
        dl=float(d.loc[idx,"lift_pp"]); vl=float(v.loc[idx,"lift_pp"])
        dn=int(d.loc[idx,"n"]); vn=int(v.loc[idx,"n"])
        if np.sign(dl)==np.sign(vl) and abs(dl)>=3 and abs(vl)>=3:
            found+=1
            print(f"{idx[0]} {idx[1]}: DISC N={dn} {dl:+.2f}pp | VAL N={vn} {vl:+.2f}pp")
    if not found: print("NONE")

    print(f"\nThresholds: {THRESH}")
    print(f"Screen:     {OUT}")
    print("RESULT: A42 QUINTILE SCREEN COMPLETE")
    print("No threshold optimization or post-hoc regrouping performed.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
