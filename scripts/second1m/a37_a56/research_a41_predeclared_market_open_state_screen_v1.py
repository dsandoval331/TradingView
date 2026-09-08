from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
BASE=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
IMP=ROOT/"ae2_market_open_impulse_v1"/"a41_market_open_impulse_features_v1.parquet"
OUTDIR=ROOT/"ae2_market_open_impulse_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a41_predeclared_state_screen_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}

def stats(x):
    n=len(x); f=int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n,f,100*f/n if n else np.nan

def main():
    b=pd.read_parquet(BASE); i=pd.read_parquet(IMP)
    for d in (b,i): d["trade_date"]=pd.to_datetime(d["trade_date"])
    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    impcols=keys+[
        "directional_spy_open_impulse_pct","directional_qqq_open_impulse_pct",
        "directional_dia_open_impulse_pct","market_open_3idx_state"
    ]
    x=b.merge(i[impcols].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    if len(x)!=len(b): raise RuntimeError("Join row parity failed.")
    if x["market_open_3idx_state"].isna().any(): raise RuntimeError("Missing A41 state after join.")

    x=x[
        x["outcome"].isin(BINARY)
        & x["session_level_clear_state"].eq("ALL_3_CLEARED")
        & x["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")
    ].copy()

    states=["ALL_3_ALIGNED","TWO_OF_3_ALIGNED","MIXED","TWO_OF_3_OPPOSING","ALL_3_OPPOSING"]
    rows=[]
    print("="*120)
    print("A41.5 - PREDECLARED MARKET-OPEN IMPULSE STATE SCREEN")
    print("="*120)
    print(f"Historical Preferred binary events: {len(x):,}")

    for period in ["DISCOVERY","VALIDATION"]:
        z=x[x["research_period"].eq(period)]
        bn,bf,br=stats(z)
        print(f"\n{period} BASELINE: N={bn}, FF={br:.2f}%")
        for state in states:
            h=z[z["market_open_3idx_state"].eq(state)]
            n,f,r=stats(h)
            lift=r-br if n else np.nan
            rows.append([period,state,n,f,r,br,lift])
            print(f"{state:20s} N={n:4d} FF={r:6.2f}% lift={lift:+6.2f}pp" if n else f"{state:20s} N=0")

    out=pd.DataFrame(rows,columns=[
        "research_period","market_open_3idx_state","n","favorable_first_n",
        "ff_pct","preferred_baseline_ff_pct","lift_pp"
    ])
    out.to_csv(OUT,index=False)

    print("\nREPLICATION SUMMARY (descriptive; no new thresholds)")
    print("-"*120)
    piv=out.pivot(index="market_open_3idx_state",columns="research_period",values=["n","ff_pct","lift_pp"])
    print(piv.to_string(float_format=lambda v:f"{v:.2f}"))

    print(f"\nOutput: {OUT}")
    print("RESULT: A41 PREDECLARED STATE SCREEN COMPLETE")
    print("No magnitude cutpoints searched. No state definitions changed.")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__=="__main__":
    main()
