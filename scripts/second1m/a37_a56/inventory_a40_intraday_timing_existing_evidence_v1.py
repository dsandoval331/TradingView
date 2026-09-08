from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path("data/second1m_alt_entry_research_v1")

SOURCES = [
    ROOT / "ae2_c2_predictors_v1" / "ae2_c2_predictor_features_v1.parquet",
    ROOT / "ae2_session_levels_robustness_v1" / "ae2_session_levels_robustness_features_v1.parquet",
]

TOKENS = [
    "time", "timestamp", "minute", "hour", "session", "rth", "open",
    "bars", "bar_", "decision", "entry", "signal", "elapsed", "since",
]

OUTDIR = ROOT / "ae2_intraday_timing_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / "a40_intraday_timing_existing_evidence_inventory_v1.csv"

def main():
    print("=" * 120)
    print("A40.1 - INTRADAY SIGNAL-TIMING EXISTING-EVIDENCE INVENTORY")
    print("=" * 120)

    rows = []

    for src in SOURCES:
        if not src.exists():
            print(f"\nMISSING SOURCE: {src}")
            continue

        df = pd.read_parquet(src)
        print(f"\nSOURCE: {src}")
        print("-" * 120)
        print(f"Rows: {len(df):,}")
        print(f"Columns: {len(df.columns):,}")

        hits = [
            c for c in df.columns
            if any(tok in c.lower() for tok in TOKENS)
        ]

        print("\nTIMING / SESSION-RELATED COLUMNS")
        for c in hits:
            print(c)
            rows.append({
                "source": str(src),
                "column": c,
                "dtype": str(df[c].dtype),
            })

        print("\nKEY FIELD AVAILABILITY")
        for c in [
            "symbol",
            "trade_date",
            "direction",
            "architecture",
            "decision_candle",
            "entry_timestamp",
            "entry_price",
            "outcome",
            "research_period",
        ]:
            print(f"{c}: {'YES' if c in df.columns else 'NO'}")

        if "entry_timestamp" in df.columns:
            ts = pd.to_datetime(df["entry_timestamp"], errors="coerce")
            print("\nENTRY_TIMESTAMP DIAGNOSTIC")
            print(f"dtype: {df['entry_timestamp'].dtype}")
            print(f"non-null parsed: {ts.notna().sum():,}")
            if ts.notna().any():
                print(f"min: {ts.min()}")
                print(f"max: {ts.max()}")
                print("sample:")
                for v in ts.dropna().head(10):
                    print(f"  {v}")

                # Outcome-free clock distribution, only to establish encoding/timezone clues.
                clock = pd.DataFrame({
                    "hour": ts.dt.hour,
                    "minute": ts.dt.minute,
                }).dropna()
                if not clock.empty:
                    print("\nENTRY CLOCK HOURS (OUTCOME-FREE)")
                    print(clock["hour"].value_counts().sort_index().to_string())

        if "decision_candle" in df.columns:
            print("\nDECISION_CANDLE VALUES (OUTCOME-FREE)")
            print(df["decision_candle"].value_counts(dropna=False).sort_index().to_string())

    pd.DataFrame(rows).drop_duplicates().to_csv(OUT, index=False)

    print("\n" + "=" * 120)
    print(f"Inventory CSV: {OUT}")
    print("RESULT: A40 INTRADAY-TIMING INVENTORY COMPLETE")
    print("No outcomes were analyzed.")
    print("No timing buckets or thresholds were created.")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
