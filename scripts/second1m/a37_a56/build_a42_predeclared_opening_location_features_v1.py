from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("data/second1m_alt_entry_research_v1")
SRC = ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
OUTDIR = ROOT/"ae2_opening_location_geometry_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR/"a42_opening_location_features_v1.parquet"
OUTCSV = OUTDIR/"a42_opening_location_features_v1.csv"

def main():
    x=pd.read_parquet(SRC)
    x["trade_date"]=pd.to_datetime(x["trade_date"])
    sign=np.where(x["direction"].eq("BULL"),1.0,-1.0)

    # Directionally relevant structural anchors.
    x["pm_dir_level"]=np.where(x["direction"].eq("BULL"),x["pmh"],x["pml"])
    x["ah_dir_level"]=np.where(x["direction"].eq("BULL"),x["ahh"],x["ahl"])
    x["pd_dir_level"]=np.where(x["direction"].eq("BULL"),x["pdh"],x["pdl"])

    # Predeclared, outcome-free A42 measurements.
    # 1) Opening displacement from prior RTH close in trade direction.
    x["a42_open_from_prior_close_dir_pct"] = sign*(x["c1_open"]/x["prior_rth_close"]-1.0)*100.0

    # 2) At 09:30, distance still remaining to each relevant breakout level.
    # Positive = level remains ahead in trade direction; negative = open already beyond it.
    for tag,col in [("pm","pm_dir_level"),("ah","ah_dir_level"),("pd","pd_dir_level")]:
        x[f"a42_open_to_{tag}_level_dir_pct"] = sign*(x[col]-x["c1_open"])/x["c1_open"]*100.0

    # 3) Distance from open to outermost relevant level in trade direction.
    # This describes how much structural distance existed ahead at the open.
    dn=pd.DataFrame({
        "pm":sign*(x["pm_dir_level"]-x["c1_open"]),
        "ah":sign*(x["ah_dir_level"]-x["c1_open"]),
        "pd":sign*(x["pd_dir_level"]-x["c1_open"]),
    },index=x.index)
    outer_idx=dn.idxmax(axis=1)
    outer_val=dn.max(axis=1)
    x["a42_open_to_outermost_dir_pct"]=outer_val/x["c1_open"]*100.0
    x["a42_outermost_level_at_open"]=outer_idx.str.upper()

    # 4) Fraction of prior-close -> outermost structural displacement already consumed by the 09:30 open.
    # No threshold/state is created; continuous measurement only.
    outer_price=np.select(
        [outer_idx.eq("pm"),outer_idx.eq("ah"),outer_idx.eq("pd")],
        [x["pm_dir_level"],x["ah_dir_level"],x["pd_dir_level"]],
        default=np.nan
    )
    denom=sign*(outer_price-x["prior_rth_close"])
    numer=sign*(x["c1_open"]-x["prior_rth_close"])
    x["a42_priorclose_to_outer_consumed_ratio"]=np.where(np.abs(denom)>1e-12,numer/denom,np.nan)

    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    cols=keys+[
        "c1_open","prior_rth_close","pm_dir_level","ah_dir_level","pd_dir_level",
        "a42_open_from_prior_close_dir_pct",
        "a42_open_to_pm_level_dir_pct","a42_open_to_ah_level_dir_pct","a42_open_to_pd_level_dir_pct",
        "a42_open_to_outermost_dir_pct","a42_outermost_level_at_open",
        "a42_priorclose_to_outer_consumed_ratio"
    ]
    feat=x[cols].copy()
    feat.to_parquet(OUT,index=False)
    feat.to_csv(OUTCSV,index=False)

    print("="*120)
    print("A42.2 - PREDECLARED OPENING-LOCATION FEATURE BUILD")
    print("="*120)
    print(f"Rows: {len(feat):,}")
    print("\nMissing values:")
    print(feat[cols[6:]].isna().sum().to_string())
    print("\nOutermost level at 09:30 (outcome-free):")
    print(feat["a42_outermost_level_at_open"].value_counts(dropna=False).to_string())
    print("\nContinuous feature descriptive statistics (outcome-free):")
    num=[c for c in cols if c.startswith("a42_") and c!="a42_outermost_level_at_open"]
    print(feat[num].describe(percentiles=[.1,.2,.25,.5,.75,.8,.9]).T.to_string())
    print(f"\nParquet: {OUT}")
    print(f"CSV:     {OUTCSV}")
    print("RESULT: A42 PREDECLARED FEATURE BUILD COMPLETE")
    print("No outcomes analyzed. No buckets or cutpoints created.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__":
    main()
