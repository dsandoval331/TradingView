from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
SRC=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
OUTDIR=ROOT/"ae2_prior_day_structure_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a44_prior_day_structure_features_v1.parquet"
CSV=OUTDIR/"a44_prior_day_structure_features_v1.csv"

def main():
    x=pd.read_parquet(SRC)
    x["trade_date"]=pd.to_datetime(x["trade_date"])
    sign=np.where(x.direction.eq("BULL"),1.0,-1.0)
    span=x["pdh"]-x["pdl"]

    # Raw prior close location: 0 = PDL, 1 = PDH.
    x["a44_prior_close_location_raw"]=np.where(span>0,(x["prior_rth_close"]-x["pdl"])/span,np.nan)

    # Direction normalized: 1 = prior close at favorable edge, 0 = adverse edge.
    x["a44_prior_close_location_dir"]=np.where(
        x.direction.eq("BULL"),
        x["a44_prior_close_location_raw"],
        1.0-x["a44_prior_close_location_raw"]
    )

    # Remaining prior-day range from prior close to the directionally relevant PD extreme.
    pd_dir=np.where(x.direction.eq("BULL"),x["pdh"],x["pdl"])
    x["a44_prior_close_to_pd_extreme_dir_pct"]=sign*(pd_dir-x["prior_rth_close"])/x["prior_rth_close"]*100.0

    # Absolute PD range as a control/structure-size measurement derived from exact PDH/PDL.
    x["a44_prior_day_range_from_levels_pct"]=span/x["prior_rth_close"]*100.0

    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    cols=keys+[
        "prior_rth_close","pdh","pdl",
        "a44_prior_close_location_raw","a44_prior_close_location_dir",
        "a44_prior_close_to_pd_extreme_dir_pct","a44_prior_day_range_from_levels_pct"
    ]
    y=x[cols].copy()
    y.to_parquet(OUT,index=False); y.to_csv(CSV,index=False)

    print("="*120)
    print("A44.2 - PREDECLARED PRIOR-DAY STRUCTURE FEATURE BUILD")
    print("="*120)
    print(f"Rows: {len(y):,}")
    print("\nMissing values:")
    print(y[cols[6:]].isna().sum().to_string())
    print("\nOutcome-free descriptive statistics:")
    nums=[c for c in cols if c.startswith("a44_")]
    print(y[nums].describe(percentiles=[.1,.2,.25,.5,.75,.8,.9]).T.to_string())
    print(f"\nParquet: {OUT}")
    print(f"CSV:     {CSV}")
    print("RESULT: A44 PREDECLARED FEATURE BUILD COMPLETE")
    print("No outcomes analyzed. No thresholds or buckets created.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
