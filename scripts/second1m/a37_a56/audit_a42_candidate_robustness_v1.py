from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
BASE=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
FEAT=ROOT/"ae2_opening_location_geometry_v1"/"a42_opening_location_features_v1.parquet"
THR=ROOT/"ae2_opening_location_geometry_v1"/"a42_discovery_quintile_thresholds_v1.csv"
OUTDIR=ROOT/"ae2_opening_location_geometry_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a42_candidate_robustness_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}
CANDS=[
 ("A42_N_PD_DISTANCE_Q5","a42_open_to_pd_level_dir_pct","Q5"),
 ("A42_N_CONSUMED_RATIO_Q2","a42_priorclose_to_outer_consumed_ratio","Q2"),
]

def stats(x):
    n=len(x); f=int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n,100*f/n if n else np.nan

def apply_q(x,col,row):
    edges=np.array([row[f"edge_{i}"] for i in range(6)],dtype=float)
    edges[0]=-np.inf; edges[-1]=np.inf
    return pd.cut(x[col],bins=edges,labels=["Q1","Q2","Q3","Q4","Q5"],include_lowest=True)

def main():
    b=pd.read_parquet(BASE); f=pd.read_parquet(FEAT); t=pd.read_csv(THR)
    for d in (b,f): d["trade_date"]=pd.to_datetime(d["trade_date"])
    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    cols=list({c for _,c,_ in CANDS})
    x=b.merge(f[keys+cols].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    x=x[x["outcome"].isin(BINARY)&x["session_level_clear_state"].eq("ALL_3_CLEARED")&
        x["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")].copy()

    for name,col,q in CANDS:
        row=t[t.feature.eq(col)].iloc[0]
        x[name]=apply_q(x,col,row).eq(q)

    # Calendar quarter from trade date, independent of outcomes.
    x["quarter"]=x["trade_date"].dt.to_period("Q").astype(str)

    rows=[]
    print("="*125)
    print("A42.4 - CANDIDATE DIRECTION / TEMPORAL ROBUSTNESS AUDIT")
    print("="*125)
    print(f"Historical Preferred binary events: {len(x):,}")

    for name,_,_ in CANDS:
        print(f"\n{name}")
        print("-"*125)
        for period in ["DISCOVERY","VALIDATION"]:
            z=x[x.research_period.eq(period)]
            bn,br=stats(z); h=z[z[name]]; n,r=stats(h)
            rows.append([name,period,"POOLED","ALL",n,r,bn,br,r-br])
            print(f"{period} POOLED: N={n} FF={r:.2f}% vs {br:.2f}% lift={r-br:+.2f}pp")
            for direction in ["BULL","BEAR"]:
                base=z[z.direction.eq(direction)]; bn2,br2=stats(base)
                hit=base[base[name]]; n2,r2=stats(hit)
                rows.append([name,period,"DIRECTION",direction,n2,r2,bn2,br2,r2-br2 if n2 else np.nan])
                print(f"  {direction}: N={n2} FF={r2:.2f}% vs {br2:.2f}% lift={r2-br2:+.2f}pp" if n2 else f"  {direction}: N=0")

        print("\nQuarter audit, all historical Preferred; report N>=8:")
        for qtr,base in x.groupby("quarter",sort=True):
            bn,br=stats(base); hit=base[base[name]]; n,r=stats(hit)
            if n>=8:
                rows.append([name,"ALL","QUARTER",qtr,n,r,bn,br,r-br])
                print(f"  {qtr}: N={n} FF={r:.2f}% vs {br:.2f}% lift={r-br:+.2f}pp")

    out=pd.DataFrame(rows,columns=[
        "candidate","research_period","split_type","split_value","candidate_n","candidate_ff_pct",
        "conditional_baseline_n","conditional_baseline_ff_pct","lift_pp"
    ])
    out.to_csv(OUT,index=False)
    print(f"\nOutput: {OUT}")
    print("RESULT: A42 CANDIDATE ROBUSTNESS AUDIT COMPLETE")
    print("No thresholds changed. No post-hoc regrouping.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
