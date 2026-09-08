from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
BASE=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
FEAT=ROOT/"ae2_prior_day_structure_v1"/"a44_prior_day_structure_features_v1.parquet"
OUTDIR=ROOT/"ae2_prior_day_structure_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
THR=OUTDIR/"a44_discovery_quintile_thresholds_v1.csv"
OUT=OUTDIR/"a44_predeclared_quintile_screen_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}

# Primary = genuinely new prior-close location inside PD range.
# Secondary = related distance-to-directional-PD-extreme.
# Control = prior-day range size, concept already represented upstream.
FEATURES=[
 ("a44_prior_close_location_dir","PRIMARY"),
 ("a44_prior_close_to_pd_extreme_dir_pct","SECONDARY"),
 ("a44_prior_day_range_from_levels_pct","CONTROL"),
]

def stats(x):
    n=len(x); f=int(x["outcome"].eq("FAVORABLE_FIRST").sum())
    return n,100*f/n if n else np.nan

def main():
    b=pd.read_parquet(BASE); f=pd.read_parquet(FEAT)
    for d in (b,f): d["trade_date"]=pd.to_datetime(d["trade_date"])
    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    cols=[c for c,_ in FEATURES]
    x=b.merge(f[keys+cols].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    x=x[x["outcome"].isin(BINARY)&
        x["session_level_clear_state"].eq("ALL_3_CLEARED")&
        x["market_prior_5d_consensus"].eq("CONSENSUS_OPPOSING")].copy()

    disc=x[x["research_period"].eq("DISCOVERY")]
    thresholds=[]
    for col,role in FEATURES:
        vals=disc[col].dropna()
        _,edges=pd.qcut(vals,5,retbins=True,duplicates="drop")
        if len(edges)!=6:
            raise RuntimeError(f"{col}: expected 5 quintiles, got {len(edges)-1}")
        thresholds.append({"feature":col,"role":role,**{f"edge_{i}":float(v) for i,v in enumerate(edges)}})
        bins=edges.astype(float).copy(); bins[0]=-np.inf; bins[-1]=np.inf
        x[col+"__A44Q"]=pd.cut(x[col],bins=bins,labels=["Q1","Q2","Q3","Q4","Q5"],include_lowest=True)
    pd.DataFrame(thresholds).to_csv(THR,index=False)

    rows=[]
    print("="*125)
    print("A44.3 - PREDECLARED DISCOVERY-FROZEN PRIOR-DAY STRUCTURE QUINTILE SCREEN")
    print("="*125)
    print(f"Historical Preferred binary events: {len(x):,}")
    print("PRIMARY: direction-normalized prior RTH close location inside PDH-PDL range.")
    print("SECONDARY: prior close -> directionally relevant PD extreme distance.")
    print("CONTROL: prior-day range size; not a new concept.")

    for period in ["DISCOVERY","VALIDATION"]:
        z=x[x["research_period"].eq(period)]
        bn,br=stats(z)
        print(f"\n{period} BASELINE: N={bn}, FF={br:.2f}%")
        for col,role in FEATURES:
            print(f"\n{role} {col}")
            for q in ["Q1","Q2","Q3","Q4","Q5"]:
                h=z[z[col+"__A44Q"].eq(q)]
                n,r=stats(h); lift=r-br if n else np.nan
                rows.append([period,col,role,q,n,r,br,lift])
                print(f"  {q}: N={n:3d} FF={r:6.2f}% lift={lift:+6.2f}pp" if n else f"  {q}: N=0")

    out=pd.DataFrame(rows,columns=[
        "research_period","feature","role","quintile","n","ff_pct","baseline_ff_pct","lift_pp"
    ])
    out.to_csv(OUT,index=False)

    print("\nNEW-FEATURE REPLICATION CELLS: same sign and |lift| >=3pp in BOTH periods")
    print("-"*125)
    for col,role in FEATURES[:2]:
        d=out[(out.research_period=="DISCOVERY")&(out.feature==col)].set_index("quintile")
        v=out[(out.research_period=="VALIDATION")&(out.feature==col)].set_index("quintile")
        found=False
        for q in ["Q1","Q2","Q3","Q4","Q5"]:
            dl=float(d.loc[q,"lift_pp"]); vl=float(v.loc[q,"lift_pp"])
            if np.sign(dl)==np.sign(vl) and abs(dl)>=3 and abs(vl)>=3:
                found=True
                print(f"{role} {col} {q}: DISC {dl:+.2f}pp N={int(d.loc[q,'n'])} | VAL {vl:+.2f}pp N={int(v.loc[q,'n'])}")
        if not found:
            print(f"{role} {col}: NONE")

    print(f"\nThresholds: {THR}")
    print(f"Screen:     {OUT}")
    print("RESULT: A44 QUINTILE SCREEN COMPLETE")
    print("No threshold optimization or post-hoc regrouping performed.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
