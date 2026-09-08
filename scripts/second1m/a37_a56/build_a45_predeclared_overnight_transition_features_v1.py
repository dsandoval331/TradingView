from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
SRC=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
OUTDIR=ROOT/"ae2_prior_day_vs_premarket_transition_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a45_overnight_transition_features_v1.parquet"
CSV=OUTDIR/"a45_overnight_transition_features_v1.csv"

def main():
    x=pd.read_parquet(SRC)
    x["trade_date"]=pd.to_datetime(x["trade_date"])
    sign=np.where(x["direction"].eq("BULL"),1.0,-1.0)

    # Stage 1: prior RTH close -> prior after-hours final close.
    x["a45_rthclose_to_ahclose_dir_pct"] = sign*(x["prior_ah_close"]/x["prior_rth_close"]-1.0)*100.0

    # Stage 2: prior AH final close -> current premarket final close.
    x["a45_ahclose_to_pmclose_dir_pct"] = sign*(x["pre_last_close"]/x["prior_ah_close"]-1.0)*100.0

    # Net overnight transition: prior RTH close -> final premarket close.
    x["a45_rthclose_to_pmclose_dir_pct"] = sign*(x["pre_last_close"]/x["prior_rth_close"]-1.0)*100.0

    # Outcome-free categorical path based only on signs of the two stages.
    s1=x["a45_rthclose_to_ahclose_dir_pct"]
    s2=x["a45_ahclose_to_pmclose_dir_pct"]
    x["a45_overnight_path_state"]=np.select(
        [
            (s1>0)&(s2>0),
            (s1<0)&(s2>0),
            (s1>0)&(s2<0),
            (s1<0)&(s2<0),
            (s1==0)|(s2==0),
        ],
        [
            "BOTH_ALIGNED",
            "AH_OPPOSING_PM_RECOVERY",
            "AH_ALIGNED_PM_REVERSAL",
            "BOTH_OPPOSING",
            "FLAT_STAGE",
        ],
        default="INCOMPLETE"
    )

    # Balance: positive means PM stage contributed more favorably than AH stage.
    x["a45_pm_minus_ah_stage_dir_pp"] = x["a45_ahclose_to_pmclose_dir_pct"] - x["a45_rthclose_to_ahclose_dir_pct"]

    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    cols=keys+[
        "prior_rth_close","prior_ah_close","pre_last_close",
        "a45_rthclose_to_ahclose_dir_pct","a45_ahclose_to_pmclose_dir_pct",
        "a45_rthclose_to_pmclose_dir_pct","a45_pm_minus_ah_stage_dir_pp",
        "a45_overnight_path_state"
    ]
    y=x[cols].copy()
    y.to_parquet(OUT,index=False); y.to_csv(CSV,index=False)

    print("="*120)
    print("A45.2 - PREDECLARED OVERNIGHT TRANSITION FEATURE BUILD")
    print("="*120)
    print(f"Rows: {len(y):,}")
    print("\nMissing values:")
    print(y[cols[6:]].isna().sum().to_string())
    print("\nOutcome-free path-state counts:")
    print(y["a45_overnight_path_state"].value_counts(dropna=False).to_string())
    print("\nOutcome-free continuous descriptive statistics:")
    nums=[c for c in cols if c.startswith("a45_") and c!="a45_overnight_path_state"]
    print(y[nums].describe(percentiles=[.1,.2,.25,.5,.75,.8,.9]).T.to_string())
    print(f"\nParquet: {OUT}")
    print(f"CSV:     {CSV}")
    print("RESULT: A45 PREDECLARED FEATURE BUILD COMPLETE")
    print("No outcomes analyzed. No outcome-derived thresholds or states created.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
