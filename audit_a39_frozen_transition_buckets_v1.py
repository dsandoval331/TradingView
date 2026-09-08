from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path("data/second1m_alt_entry_research_v1")
SRC = ROOT / "ae2_c2_predictors_v1" / "ae2_c2_predictor_features_v1.parquet"
OUTDIR = ROOT / "ae2_c1_c2_transition_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)

FIELDS = [
    "c1_to_c2_close_progress_pct",
    "c2_to_c1_volume_ratio",
    "clv_change_pp",
    "vwap_distance_change_pp",
]

def main():
    df = pd.read_parquet(SRC)
    print("=" * 118)
    print("A39.2 - FROZEN TRANSITION-BUCKET DEFINITION / AVAILABILITY AUDIT")
    print("=" * 118)
    print(f"Source: {SRC}")
    print(f"Rows: {len(df):,}")

    rows = []
    for f in FIELDS:
        b = f + "__bucket"
        print("\n" + f)
        print("-" * 118)
        if f not in df.columns or b not in df.columns:
            print("MISSING FIELD OR BUCKET")
            continue

        tmp = df[[f,b]].copy()
        tmp[f] = pd.to_numeric(tmp[f], errors="coerce")
        g = (
            tmp.dropna(subset=[b])
               .groupby(b, dropna=False, observed=True)
               .agg(
                   n=(f,"size"),
                   non_null_n=(f,"count"),
                   min_value=(f,"min"),
                   max_value=(f,"max"),
                   median_value=(f,"median"),
               )
               .reset_index()
        )
        print(g.to_string(index=False, float_format=lambda x: f"{x:.6f}"))

        for _, r in g.iterrows():
            rows.append({
                "feature": f,
                "bucket": r[b],
                "n": int(r["n"]),
                "non_null_n": int(r["non_null_n"]),
                "min_value": r["min_value"],
                "max_value": r["max_value"],
                "median_value": r["median_value"],
            })

    out = pd.DataFrame(rows)
    outfile = OUTDIR / "a39_frozen_transition_bucket_inventory_v1.csv"
    out.to_csv(outfile, index=False)

    print("\n" + "=" * 118)
    print(f"Inventory CSV: {outfile}")
    print("RESULT: FROZEN TRANSITION BUCKET AUDIT COMPLETE")
    print("No outcomes were analyzed. No thresholds were created/recomputed.")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
