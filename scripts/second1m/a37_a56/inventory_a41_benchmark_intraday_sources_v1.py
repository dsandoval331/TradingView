from pathlib import Path
import pandas as pd

ROOT = Path("data/second1m_alt_entry_research_v1")
OUTDIR = ROOT / "ae2_market_open_impulse_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / "a41_benchmark_intraday_source_inventory_v1.csv"

TOKENS = ["spy", "qqq", "dia", "benchmark", "market", "intraday", "minute", "1m"]

def main():
    print("=" * 120)
    print("A41.2 - BENCHMARK INTRADAY SOURCE INVENTORY")
    print("=" * 120)

    candidates = []
    search_roots = [Path("data"), ROOT]

    seen = set()
    for base in search_roots:
        if not base.exists():
            continue
        for p in base.rglob("*.parquet"):
            if p in seen:
                continue
            seen.add(p)
            low = str(p).lower()
            if any(t in low for t in TOKENS):
                candidates.append(p)

    rows = []
    for p in sorted(candidates):
        try:
            df = pd.read_parquet(p)
        except Exception:
            continue

        cols = df.columns.tolist()
        lc = {c.lower(): c for c in cols}
        symbol_cols = [c for c in cols if c.lower() in {"symbol","ticker"}]
        time_cols = [c for c in cols if any(t in c.lower() for t in ["timestamp","datetime","time"])]
        ohlc = [c for c in cols if c.lower() in {"open","high","low","close","volume"}]

        symbol_values = ""
        if symbol_cols:
            try:
                vals = df[symbol_cols[0]].dropna().astype(str).unique()[:20]
                symbol_values = ",".join(vals)
            except Exception:
                pass

        relevant = (
            len(time_cols) > 0 and len(ohlc) >= 4 and
            (any(x in symbol_values.upper().split(",") for x in ["SPY","QQQ","DIA"])
             or any(t in str(p).lower() for t in ["spy","qqq","dia","benchmark","market_intraday"]))
        )
        if not relevant:
            continue

        print(f"\nSOURCE: {p}")
        print("-" * 120)
        print(f"Rows: {len(df):,}")
        print(f"Symbol columns: {symbol_cols}")
        print(f"Time columns: {time_cols}")
        print(f"OHLCV columns: {ohlc}")
        print(f"Sample symbols: {symbol_values}")

        rows.append({
            "source": str(p),
            "rows": len(df),
            "symbol_columns": "|".join(symbol_cols),
            "time_columns": "|".join(time_cols),
            "ohlcv_columns": "|".join(ohlc),
            "sample_symbols": symbol_values,
        })

    pd.DataFrame(rows).to_csv(OUT, index=False)

    print("\n" + "=" * 120)
    print(f"Inventory CSV: {OUT}")
    if rows:
        print("RESULT: BENCHMARK INTRADAY CANDIDATE SOURCES FOUND")
    else:
        print("RESULT: NO LOCAL BENCHMARK INTRADAY PARQUET FOUND")
    print("No outcomes were analyzed. No market-open impulse feature was created.")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
