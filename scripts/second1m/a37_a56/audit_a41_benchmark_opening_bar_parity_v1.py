from pathlib import Path
import pandas as pd

CACHE = Path("data/second1m_alt_entry_cache_v1")
FILES = {
    "SPY": [CACHE/"partitions/SPY/SPY_2025.parquet", CACHE/"partitions/SPY/SPY_2026.parquet"],
    "QQQ": [CACHE/"partitions/QQQ/QQQ_2025.parquet", CACHE/"partitions/QQQ/QQQ_2026.parquet"],
    "DIA": [CACHE/"DIA/DIA_2025.parquet", CACHE/"DIA/DIA_2026.parquet"],
}
OUTDIR = Path("data/second1m_alt_entry_research_v1/ae2_market_open_impulse_v1")
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR/"a41_benchmark_opening_bar_parity_v1.csv"

def main():
    rows=[]
    print("="*120)
    print("A41.3 - BENCHMARK OPENING-BAR / TIMESTAMP PARITY AUDIT")
    print("="*120)

    for sym, files in FILES.items():
        for p in files:
            if not p.exists():
                print(f"\nMISSING: {p}")
                continue
            df=pd.read_parquet(p)
            print(f"\n{sym} SOURCE: {p}")
            print("-"*120)
            print(f"Rows: {len(df):,}")
            print(f"Columns: {list(df.columns)}")
            if "timeframe" in df.columns:
                print("timeframe counts:")
                print(df["timeframe"].value_counts(dropna=False).head(10).to_string())

            tcol="timestamp_utc" if "timestamp_utc" in df.columns else None
            if tcol is None:
                print("No timestamp_utc; STOP for this source.")
                continue
            ts=pd.to_datetime(df[tcol],utc=True,errors="coerce")
            print(f"timestamp dtype raw: {df[tcol].dtype}")
            print(f"parsed non-null: {ts.notna().sum():,}")
            print("first 12 parsed timestamps:")
            for v in ts.dropna().head(12):
                print(" ",v)

            # Convert to New York to establish exact opening-bar encoding.
            et=ts.dt.tz_convert("America/New_York")
            sample=pd.DataFrame({"date":et.dt.date,"hour":et.dt.hour,"minute":et.dt.minute})
            rth=sample[(sample["hour"]==9)&(sample["minute"].isin([30,31,32]))]
            counts=rth.groupby(["hour","minute"]).size()
            print("09:30/09:31/09:32 ET bar counts:")
            print(counts.to_string() if len(counts) else "NONE")

            dates=sample["date"].nunique()
            for minute in [30,31]:
                n_dates=sample[(sample.hour==9)&(sample.minute==minute)]["date"].nunique()
                rows.append({
                    "symbol":sym,"source":str(p),"minute_et":f"09:{minute:02d}",
                    "unique_dates_total":dates,"unique_dates_with_bar":n_dates,
                    "coverage_pct":100*n_dates/dates if dates else None
                })

    pd.DataFrame(rows).to_csv(OUT,index=False)
    print("\n"+"="*120)
    print(f"Output: {OUT}")
    print("RESULT: BENCHMARK OPENING-BAR PARITY AUDIT COMPLETE")
    print("No outcomes analyzed. No impulse thresholds/states created.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__":
    main()
