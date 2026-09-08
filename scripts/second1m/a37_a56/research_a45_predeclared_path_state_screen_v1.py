from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
BASE=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
FEAT=ROOT/"ae2_prior_day_vs_premarket_transition_v1"/"a45_overnight_transition_features_v1.parquet"
OUTDIR=ROOT/"ae2_prior_day_vs_premarket_transition_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a45_predeclared_path_state_screen_v1.csv"
BINARY={"FAVORABLE_FIRST","ADVERSE_FIRST"}
STATES=["BOTH_ALIGNED","AH_OPPOSING_PM_RECOVERY","AH_ALIGNED_PM_REVERSAL","BOTH_OPPOSING","FLAT_STAGE","INCOMPLETE"]

def stats(x):
    n=len(x); f=int(x.outcome.eq("FAVORABLE_FIRST").sum())
    return n,100*f/n if n else np.nan

def main():
    b=pd.read_parquet(BASE); f=pd.read_parquet(FEAT)
    for d in (b,f): d["trade_date"]=pd.to_datetime(d["trade_date"])
    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    x=b.merge(f[keys+["a45_overnight_path_state"]].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    x=x[x.outcome.isin(BINARY)&x.session_level_clear_state.eq("ALL_3_CLEARED")&
        x.market_prior_5d_consensus.eq("CONSENSUS_OPPOSING")].copy()

    rows=[]
    print("="*125)
    print("A45.3 - PREDECLARED OVERNIGHT PATH-STATE OUTCOME SCREEN")
    print("="*125)
    print(f"Historical Preferred binary events: {len(x):,}")
    print("States were frozen before outcome exposure; no magnitude thresholds are used.")

    for period in ["DISCOVERY","VALIDATION"]:
        z=x[x.research_period.eq(period)]; bn,br=stats(z)
        print(f"\n{period} BASELINE: N={bn}, FF={br:.2f}%")
        for s in STATES:
            h=z[z.a45_overnight_path_state.eq(s)]; n,r=stats(h); lift=r-br if n else np.nan
            rows.append([period,s,n,r,br,lift])
            print(f"{s:25s} N={n:3d} FF={r:6.2f}% lift={lift:+6.2f}pp" if n else f"{s:25s} N=0")

    out=pd.DataFrame(rows,columns=["research_period","path_state","n","ff_pct","baseline_ff_pct","lift_pp"])
    out.to_csv(OUT,index=False)

    print("\nPREDECLARED HYPOTHESIS CHECK")
    print("-"*125)
    print("Expected: BOTH_ALIGNED strongest; BOTH_OPPOSING weakest.")
    print("Mixed-state comparison of interest: AH_OPPOSING_PM_RECOVERY vs AH_ALIGNED_PM_REVERSAL.")
    print("A state may advance only if its effect is directionally consistent discovery -> validation with meaningful N;")
    print("do not regroup states after seeing outcomes.")

    print(f"\nOutput: {OUT}")
    print("RESULT: A45 PATH-STATE SCREEN COMPLETE")
    print("No threshold optimization or post-hoc regrouping performed.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
