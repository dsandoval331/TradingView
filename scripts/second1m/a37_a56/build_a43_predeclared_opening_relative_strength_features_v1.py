from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
BASE=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
A41=ROOT/"ae2_market_open_impulse_v1"/"a41_market_open_impulse_features_v1.parquet"
OUTDIR=ROOT/"ae2_opening_relative_strength_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a43_opening_relative_strength_features_v1.parquet"
CSV=OUTDIR/"a43_opening_relative_strength_features_v1.csv"

def main():
    b=pd.read_parquet(BASE); m=pd.read_parquet(A41)
    for d in (b,m): d["trade_date"]=pd.to_datetime(d["trade_date"])
    keys=["symbol","trade_date","direction","architecture","decision_candle","entry_timestamp"]
    mcols=keys+["directional_spy_open_impulse_pct","directional_qqq_open_impulse_pct","directional_dia_open_impulse_pct"]
    x=b.merge(m[mcols].drop_duplicates(keys),on=keys,how="left",validate="one_to_one")
    sign=np.where(x.direction.eq("BULL"),1.0,-1.0)

    # Stock impulse over the exact same 09:30 open -> 09:31 close window as A41.
    x["a43_directional_stock_open_impulse_pct"]=sign*(x["c2_close"]/x["c1_open"]-1)*100
    x["a43_directional_market_avg_open_impulse_pct"]=x[
        ["directional_spy_open_impulse_pct","directional_qqq_open_impulse_pct","directional_dia_open_impulse_pct"]
    ].mean(axis=1)
    x["a43_stock_vs_spy_open_rs_pp"]=x["a43_directional_stock_open_impulse_pct"]-x["directional_spy_open_impulse_pct"]
    x["a43_stock_vs_qqq_open_rs_pp"]=x["a43_directional_stock_open_impulse_pct"]-x["directional_qqq_open_impulse_pct"]
    x["a43_stock_vs_dia_open_rs_pp"]=x["a43_directional_stock_open_impulse_pct"]-x["directional_dia_open_impulse_pct"]
    x["a43_stock_vs_market_avg_open_rs_pp"]=x["a43_directional_stock_open_impulse_pct"]-x["a43_directional_market_avg_open_impulse_pct"]

    cols=keys+[
        "a43_directional_stock_open_impulse_pct",
        "directional_spy_open_impulse_pct","directional_qqq_open_impulse_pct","directional_dia_open_impulse_pct",
        "a43_directional_market_avg_open_impulse_pct",
        "a43_stock_vs_spy_open_rs_pp","a43_stock_vs_qqq_open_rs_pp",
        "a43_stock_vs_dia_open_rs_pp","a43_stock_vs_market_avg_open_rs_pp"
    ]
    y=x[cols].copy()
    y.to_parquet(OUT,index=False); y.to_csv(CSV,index=False)

    print("="*120)
    print("A43.2 - PREDECLARED STOCK-vs-MARKET OPENING RELATIVE-STRENGTH FEATURE BUILD")
    print("="*120)
    print(f"Rows: {len(y):,}")
    print("\nMissing values:")
    print(y[cols[6:]].isna().sum().to_string())
    print("\nOutcome-free descriptive statistics:")
    nums=[c for c in cols if c.startswith("a43_")]
    print(y[nums].describe(percentiles=[.1,.2,.25,.5,.75,.8,.9]).T.to_string())
    print(f"\nParquet: {OUT}")
    print(f"CSV:     {CSV}")
    print("RESULT: A43 PREDECLARED FEATURE BUILD COMPLETE")
    print("No outcomes analyzed. No thresholds or buckets created.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
