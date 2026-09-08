from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("data/second1m_alt_entry_research_v1")
CACHE = Path("data/second1m_alt_entry_cache_v1")
EVENTS = ROOT / "ae2_session_levels_robustness_v1" / "ae2_session_levels_robustness_features_v1.parquet"
OUTDIR = ROOT / "ae2_market_open_impulse_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)

OUT_FEATURES = OUTDIR / "a41_market_open_impulse_features_v1.parquet"
OUT_CSV = OUTDIR / "a41_market_open_impulse_features_v1.csv"
OUT_COVERAGE = OUTDIR / "a41_market_open_impulse_coverage_v1.csv"

FILES = {
    "SPY": [
        CACHE / "partitions/SPY/SPY_2025.parquet",
        CACHE / "partitions/SPY/SPY_2026.parquet",
    ],
    "QQQ": [
        CACHE / "partitions/QQQ/QQQ_2025.parquet",
        CACHE / "partitions/QQQ/QQQ_2026.parquet",
    ],
    "DIA": [
        CACHE / "DIA/DIA_2025.parquet",
        CACHE / "DIA/DIA_2026.parquet",
    ],
}

def load_index_open_impulse(symbol: str, paths: list[Path]) -> pd.DataFrame:
    frames = []
    for p in paths:
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        ts = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
        et = ts.dt.tz_convert("America/New_York")
        x = df.copy()
        x["_et"] = et
        x["_date"] = et.dt.date
        x["_hour"] = et.dt.hour
        x["_minute"] = et.dt.minute

        o930 = x[(x["_hour"] == 9) & (x["_minute"] == 30)][["_date","open"]].copy()
        c931 = x[(x["_hour"] == 9) & (x["_minute"] == 31)][["_date","close"]].copy()

        o930 = o930.rename(columns={"open": f"{symbol.lower()}_0930_open"})
        c931 = c931.rename(columns={"close": f"{symbol.lower()}_0931_close"})

        one = o930.merge(c931, on="_date", how="inner", validate="one_to_one")
        one["trade_date"] = pd.to_datetime(one["_date"])
        one[f"{symbol.lower()}_open_impulse_pct"] = (
            (one[f"{symbol.lower()}_0931_close"] / one[f"{symbol.lower()}_0930_open"]) - 1.0
        ) * 100.0
        frames.append(one.drop(columns=["_date"]))

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values("trade_date").drop_duplicates("trade_date", keep="last")
    return out

def classify_row(row) -> str:
    vals = [
        row["directional_spy_open_impulse_pct"],
        row["directional_qqq_open_impulse_pct"],
        row["directional_dia_open_impulse_pct"],
    ]
    if any(pd.isna(v) for v in vals):
        return "INCOMPLETE"

    aligned = sum(v > 0 for v in vals)
    opposing = sum(v < 0 for v in vals)
    flat = 3 - aligned - opposing

    if aligned == 3:
        return "ALL_3_ALIGNED"
    if opposing == 3:
        return "ALL_3_OPPOSING"
    if aligned == 2:
        return "TWO_OF_3_ALIGNED"
    if opposing == 2:
        return "TWO_OF_3_OPPOSING"
    return "MIXED"

def main():
    print("=" * 120)
    print("A41.4 - BUILD FROZEN MARKET-OPEN IMPULSE FEATURE + COVERAGE AUDIT")
    print("=" * 120)
    print("Predeclared measurement: index 09:30 ET open -> 09:31 ET close.")
    print("No magnitude threshold. State uses direction-normalized sign only.")

    ev = pd.read_parquet(EVENTS)
    ev["trade_date"] = pd.to_datetime(ev["trade_date"])
    print(f"Event rows: {len(ev):,}")

    merged = ev.copy()

    coverage_rows = []
    for sym, paths in FILES.items():
        idx = load_index_open_impulse(sym, paths)
        print(f"{sym} index dates with complete 09:30 open + 09:31 close: {len(idx):,}")
        merged = merged.merge(idx, on="trade_date", how="left", validate="many_to_one")

        c = f"{sym.lower()}_open_impulse_pct"
        coverage_rows.append({
            "symbol": sym,
            "event_rows": len(merged),
            "event_rows_with_impulse": int(merged[c].notna().sum()),
            "event_rows_missing_impulse": int(merged[c].isna().sum()),
            "coverage_pct": 100.0 * merged[c].notna().mean(),
        })

    sign = np.where(merged["direction"].eq("BULL"), 1.0, -1.0)
    for sym in ["spy","qqq","dia"]:
        merged[f"directional_{sym}_open_impulse_pct"] = merged[f"{sym}_open_impulse_pct"] * sign

    merged["market_open_3idx_state"] = merged.apply(classify_row, axis=1)

    keycols = [
        "symbol","trade_date","direction","architecture","decision_candle","entry_timestamp",
        "spy_0930_open","spy_0931_close","spy_open_impulse_pct","directional_spy_open_impulse_pct",
        "qqq_0930_open","qqq_0931_close","qqq_open_impulse_pct","directional_qqq_open_impulse_pct",
        "dia_0930_open","dia_0931_close","dia_open_impulse_pct","directional_dia_open_impulse_pct",
        "market_open_3idx_state",
    ]
    feat = merged[keycols].copy()

    feat.to_parquet(OUT_FEATURES, index=False)
    feat.to_csv(OUT_CSV, index=False)

    coverage = pd.DataFrame(coverage_rows)
    coverage.to_csv(OUT_COVERAGE, index=False)

    print("\nCOVERAGE")
    print("-" * 120)
    print(coverage.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print("\nMARKET OPEN 3-INDEX STATE COUNTS — ALL AE2 EVENTS, OUTCOME-FREE")
    print("-" * 120)
    print(feat["market_open_3idx_state"].value_counts(dropna=False).to_string())

    incomplete_dates = feat.loc[
        feat["market_open_3idx_state"].eq("INCOMPLETE"),
        ["trade_date"]
    ].drop_duplicates().sort_values("trade_date")

    print(f"\nIncomplete unique trade dates: {len(incomplete_dates):,}")
    if len(incomplete_dates):
        print(incomplete_dates.to_string(index=False))

    print(f"\nFeatures parquet: {OUT_FEATURES}")
    print(f"Features CSV:     {OUT_CSV}")
    print(f"Coverage CSV:     {OUT_COVERAGE}")
    print("RESULT: A41 MARKET-OPEN IMPULSE FEATURE BUILD COMPLETE")
    print("No outcomes were analyzed.")
    print("No outcome-derived thresholds were created.")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
