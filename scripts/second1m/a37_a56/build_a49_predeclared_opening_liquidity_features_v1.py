from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
SRC=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
OUTDIR=ROOT/"ae2_opening_liquidity_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a49_opening_liquidity_features_v1.parquet"
CSV=OUTDIR/"a49_opening_liquidity_features_v1.csv"

def main():
    x=pd.read_parquet(SRC)
    x["trade_date"]=pd.to_datetime(x["trade_date"])

    # Approximate first-two-minute notional turnover using each minute's close as price proxy.
    x["a49_opening_2m_dollar_activity"] = (
        x["c1_volume"] * x["c1_close"] + x["c2_volume"] * x["c2_close"]
    )

    # Cross-sectional size proxy: log10 notional makes the highly skewed dollar distribution interpretable.
    x["a49_log10_opening_2m_dollar_activity"] = np.where(
        x["a49_opening_2m_dollar_activity"] > 0,
        np.log10(x["a49_opening_2m_dollar_activity"]),
        np.nan
    )

    # Price level is retained explicitly for later redundancy interpretation.
    x["a49_log10_entry_price"] = np.where(
        x["entry_price"] > 0, np.log10(x["entry_price"]), np.nan
    )

    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    cols=keys+[
        "c1_close","c2_close","c1_volume","c2_volume","opening_2m_volume",
        "entry_price","opening_2m_rvol_20d",
        "a49_opening_2m_dollar_activity",
        "a49_log10_opening_2m_dollar_activity",
        "a49_log10_entry_price"
    ]
    y=x[cols].copy()
    y.to_parquet(OUT,index=False); y.to_csv(CSV,index=False)

    print("="*120)
    print("A49.2 - PREDECLARED OPENING LIQUIDITY / DOLLAR-ACTIVITY FEATURE BUILD")
    print("="*120)
    print(f"Rows: {len(y):,}")
    print("\nMissing values:")
    print(y[cols[6:]].isna().sum().to_string())
    print("\nOutcome-free descriptive statistics:")
    nums=["opening_2m_volume","entry_price","opening_2m_rvol_20d",
          "a49_opening_2m_dollar_activity","a49_log10_opening_2m_dollar_activity",
          "a49_log10_entry_price"]
    print(y[nums].describe(percentiles=[.1,.2,.25,.5,.75,.8,.9]).T.to_string())

    valid=y[["a49_log10_opening_2m_dollar_activity","opening_2m_rvol_20d",
             "a49_log10_entry_price","opening_2m_volume"]].dropna()
    print("\nOutcome-free Pearson correlations:")
    print(valid.corr().to_string())

    print(f"\nParquet: {OUT}")
    print(f"CSV:     {CSV}")
    print("RESULT: A49 PREDECLARED FEATURE BUILD COMPLETE")
    print("No outcomes analyzed. No thresholds/buckets created.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
