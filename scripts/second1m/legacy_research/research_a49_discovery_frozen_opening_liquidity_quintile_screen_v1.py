from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
BASE=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
FEAT=ROOT/"ae2_opening_liquidity_v1"/"a49_opening_liquidity_features_v1.parquet"
OUTDIR=ROOT/"ae2_opening_liquidity_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
THR=OUTDIR/"a49_discovery_quintile_thresholds_v1.csv"
OUT=OUTDIR/"a49_predeclared_quintile_screen_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}
FEATURE="a49_log10_opening_2m_dollar_activity"

def stat(z):
    n=len(z); f=int(z.outcome.eq("FAVORABLE_FIRST").sum())
    return n,(100*f/n if n else np.nan)

def main():
    b=pd.read_parquet(BASE); f=pd.read_parquet(FEAT)
    for d in (b,f): d["trade_date"]=pd.to_datetime(d["trade_date"])
    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    x=b.merge(f[keys+[FEATURE]].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    x=x[x.outcome.isin(BINARY)&x.session_level_clear_state.eq("ALL_3_CLEARED")&
        x.market_prior_5d_consensus.eq("CONSENSUS_OPPOSING")].copy()

    disc=x[x.research_period.eq("DISCOVERY")]
    _,edges=pd.qcut(disc[FEATURE].dropna(),5,retbins=True,duplicates="drop")
    if len(edges)!=6: raise RuntimeError(f"Expected 5 quintiles, got {len(edges)-1}")
    pd.DataFrame([{"feature":FEATURE,**{f"edge_{i}":float(v) for i,v in enumerate(edges)}}]).to_csv(THR,index=False)
    bins=edges.copy(); bins[0]=-np.inf; bins[-1]=np.inf
    x["a49_liquidity_q"]=pd.cut(x[FEATURE],bins=bins,labels=["Q1","Q2","Q3","Q4","Q5"],include_lowest=True)

    rows=[]
    print("="*122)
    print("A49.3 - PREDECLARED DISCOVERY-FROZEN OPENING DOLLAR-ACTIVITY QUINTILE SCREEN")
    print("="*122)
    print(f"Historical Preferred binary events: {len(x):,}")
    print("Q1 = lowest opening dollar activity; Q5 = highest.")
    for period in ["DISCOVERY","VALIDATION"]:
        z=x[x.research_period.eq(period)]; bn,br=stat(z)
        print(f"\n{period} BASELINE: N={bn}, FF={br:.2f}%")
        for q in ["Q1","Q2","Q3","Q4","Q5"]:
            h=z[z.a49_liquidity_q.eq(q)]; n,r=stat(h); lift=r-br if n else np.nan
            rows.append([period,q,n,r,br,lift])
            print(f"  {q}: N={n:3d} FF={r:6.2f}% lift={lift:+6.2f}pp")
    out=pd.DataFrame(rows,columns=["research_period","quintile","n","ff_pct","baseline_ff_pct","lift_pp"])
    out.to_csv(OUT,index=False)

    d=out[out.research_period.eq("DISCOVERY")].set_index("quintile")
    v=out[out.research_period.eq("VALIDATION")].set_index("quintile")
    print("\nREPLICATION CELLS: same sign and |lift| >=3pp in BOTH periods")
    print("-"*122)
    found=False
    for q in ["Q1","Q2","Q3","Q4","Q5"]:
        dl=float(d.loc[q,"lift_pp"]); vl=float(v.loc[q,"lift_pp"])
        if np.sign(dl)==np.sign(vl) and abs(dl)>=3 and abs(vl)>=3:
            found=True
            print(f"{q}: DISC {dl:+.2f}pp N={int(d.loc[q,'n'])} | VAL {vl:+.2f}pp N={int(v.loc[q,'n'])}")
    if not found: print("NONE")

    print(f"\nThresholds: {THR}")
    print(f"Screen:     {OUT}")
    print("RESULT: A49 QUINTILE SCREEN COMPLETE")
    print("Do not run redundancy/robustness unless a predeclared quintile replicates.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
