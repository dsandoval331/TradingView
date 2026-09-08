from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
BASE=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
FEAT=ROOT/"ae2_opening_relative_strength_v1"/"a43_opening_relative_strength_features_v1.parquet"
OUTDIR=ROOT/"ae2_opening_relative_strength_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
THR=OUTDIR/"a43_discovery_quintile_thresholds_v1.csv"
OUT=OUTDIR/"a43_predeclared_quintile_screen_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}

PRIMARY="a43_stock_vs_market_avg_open_rs_pp"
ROBUST=[
 "a43_stock_vs_spy_open_rs_pp",
 "a43_stock_vs_qqq_open_rs_pp",
 "a43_stock_vs_dia_open_rs_pp",
]
FEATURES=[PRIMARY]+ROBUST

def stats(x):
    n=len(x); f=int(x.outcome.eq("FAVORABLE_FIRST").sum())
    return n,100*f/n if n else np.nan

def main():
    b=pd.read_parquet(BASE); f=pd.read_parquet(FEAT)
    for d in (b,f): d["trade_date"]=pd.to_datetime(d["trade_date"])
    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    x=b.merge(f[keys+FEATURES].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    x=x[x.outcome.isin(BINARY)&x.session_level_clear_state.eq("ALL_3_CLEARED")&
        x.market_prior_5d_consensus.eq("CONSENSUS_OPPOSING")].copy()

    disc=x[x.research_period.eq("DISCOVERY")]
    thresholds=[]
    for col in FEATURES:
        _,edges=pd.qcut(disc[col],5,retbins=True,duplicates="drop")
        if len(edges)!=6: raise RuntimeError(f"{col}: expected five quintiles")
        thresholds.append({"feature":col,**{f"edge_{i}":float(v) for i,v in enumerate(edges)}})
        e=edges.astype(float); e[0]=-np.inf; e[-1]=np.inf
        x[col+"__A43Q"]=pd.cut(x[col],e,labels=["Q1","Q2","Q3","Q4","Q5"],include_lowest=True)
    pd.DataFrame(thresholds).to_csv(THR,index=False)

    rows=[]
    print("="*125)
    print("A43.3 - PREDECLARED DISCOVERY-FROZEN OPENING RELATIVE-STRENGTH QUINTILE SCREEN")
    print("="*125)
    print(f"Historical Preferred binary events: {len(x):,}")
    print("PRIMARY: stock minus 3-index average opening impulse.")
    print("SPY/QQQ/DIA are predeclared robustness comparisons, not alternate-model searches.")

    for period in ["DISCOVERY","VALIDATION"]:
        z=x[x.research_period.eq(period)]; bn,br=stats(z)
        print(f"\n{period} BASELINE: N={bn}, FF={br:.2f}%")
        for col in FEATURES:
            label="PRIMARY" if col==PRIMARY else "ROBUSTNESS"
            print(f"\n{label} {col}")
            for q in ["Q1","Q2","Q3","Q4","Q5"]:
                h=z[z[col+"__A43Q"].eq(q)]; n,r=stats(h); lift=r-br if n else np.nan
                rows.append([period,col,label,q,n,r,br,lift])
                print(f"  {q}: N={n:3d} FF={r:6.2f}% lift={lift:+6.2f}pp" if n else f"  {q}: N=0")

    out=pd.DataFrame(rows,columns=["research_period","feature","role","quintile","n","ff_pct","baseline_ff_pct","lift_pp"])
    out.to_csv(OUT,index=False)

    print("\nPRIMARY REPLICATION CELLS: same sign and |lift| >=3pp in discovery AND validation")
    print("-"*125)
    d=out[(out.research_period=="DISCOVERY")&(out.feature==PRIMARY)].set_index("quintile")
    v=out[(out.research_period=="VALIDATION")&(out.feature==PRIMARY)].set_index("quintile")
    found=False
    for q in d.index:
        dl=float(d.loc[q,"lift_pp"]); vl=float(v.loc[q,"lift_pp"])
        if np.sign(dl)==np.sign(vl) and abs(dl)>=3 and abs(vl)>=3:
            found=True
            print(f"{q}: DISC {dl:+.2f}pp N={int(d.loc[q,'n'])} | VAL {vl:+.2f}pp N={int(v.loc[q,'n'])}")
    if not found: print("NONE")

    print("\nPREDECLARED HYPOTHESIS CHECK")
    print("Expected general tendency: higher opening relative strength favorable; lower relative strength unfavorable.")
    print("Do not rescue a failed primary result by selecting whichever individual index looks best.")

    print(f"\nThresholds: {THR}")
    print(f"Screen:     {OUT}")
    print("RESULT: A43 QUINTILE SCREEN COMPLETE")
    print("No threshold optimization or post-hoc regrouping performed.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
