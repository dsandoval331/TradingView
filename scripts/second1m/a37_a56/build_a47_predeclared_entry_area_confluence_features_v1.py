from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
SRC=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
OUTDIR=ROOT/"ae2_level_confluence_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a47_entry_area_confluence_features_v1.parquet"
CSV=OUTDIR/"a47_entry_area_confluence_features_v1.csv"

def pct_abs(a,b,den):
    return (a-b).abs()/den.abs()*100.0

def main():
    x=pd.read_parquet(SRC)
    x["trade_date"]=pd.to_datetime(x["trade_date"])

    # Canonical center of the three directionally relevant PM/AH/PD levels.
    levels=x[["pm_directional_level","ah_directional_level","pd_directional_level"]]
    x["a47_structural_center_price"]=levels.mean(axis=1,skipna=False)

    # Absolute proximity of that structural center to contemporaneous technical references.
    den=x["a47_structural_center_price"]
    x["a47_center_to_ema9_abs_pct"]=pct_abs(den,x["ema9"],den)
    x["a47_center_to_ema20_abs_pct"]=pct_abs(den,x["ema20"],den)
    x["a47_center_to_vwap_abs_pct"]=pct_abs(den,x["c2_vwap"],den)

    # Compact summaries, predeclared before outcomes.
    tech=x[["ema9","ema20","c2_vwap"]]
    x["a47_center_to_nearest_tech_abs_pct"]=pd.concat([
        x["a47_center_to_ema9_abs_pct"],
        x["a47_center_to_ema20_abs_pct"],
        x["a47_center_to_vwap_abs_pct"]
    ],axis=1).min(axis=1)
    x["a47_center_to_mean_tech_abs_pct"]=pd.concat([
        x["a47_center_to_ema9_abs_pct"],
        x["a47_center_to_ema20_abs_pct"],
        x["a47_center_to_vwap_abs_pct"]
    ],axis=1).mean(axis=1)

    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    cols=keys+[
        "pm_directional_level","ah_directional_level","pd_directional_level",
        "ema9","ema20","c2_vwap","a47_structural_center_price",
        "a47_center_to_ema9_abs_pct","a47_center_to_ema20_abs_pct",
        "a47_center_to_vwap_abs_pct","a47_center_to_nearest_tech_abs_pct",
        "a47_center_to_mean_tech_abs_pct"
    ]
    y=x[cols].copy()
    y.to_parquet(OUT,index=False); y.to_csv(CSV,index=False)

    print("="*120)
    print("A47.2 - PREDECLARED ENTRY-AREA TECHNICAL CONFLUENCE FEATURE BUILD")
    print("="*120)
    print(f"Rows: {len(y):,}")
    print("\nMissing values:")
    print(y[cols[6:]].isna().sum().to_string())
    nums=[c for c in cols if c.startswith("a47_") and c!="a47_structural_center_price"]
    print("\nOutcome-free descriptive statistics:")
    print(y[nums].describe(percentiles=[.1,.2,.25,.5,.75,.8,.9]).T.to_string())
    print(f"\nParquet: {OUT}")
    print(f"CSV:     {CSV}")
    print("RESULT: A47 PREDECLARED FEATURE BUILD COMPLETE")
    print("No outcomes analyzed. No thresholds/buckets created.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
