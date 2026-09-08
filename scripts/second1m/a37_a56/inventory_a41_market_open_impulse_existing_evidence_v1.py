from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path("data/second1m_alt_entry_research_v1")
SRC = ROOT / "ae2_session_levels_robustness_v1" / "ae2_session_levels_robustness_features_v1.parquet"
OUTDIR = ROOT / "ae2_market_open_impulse_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / "a41_market_open_impulse_existing_evidence_inventory_v1.csv"

TOKENS = [
    "spy", "qqq", "dia", "market", "index", "indices", "3idx",
    "opening", "open_", "_open", "return", "ret_", "_ret",
    "impulse", "breadth", "aligned", "opposing", "mixed"
]

def main():
    df = pd.read_parquet(SRC)
    print("=" * 120)
    print("A41.1 - MARKET-OPEN IMPULSE / CROSS-INDEX EXISTING-EVIDENCE INVENTORY")
    print("=" * 120)
    print(f"Source: {SRC}")
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns):,}")

    hits = [c for c in df.columns if any(t in c.lower() for t in TOKENS)]
    rows = []

    print("\nMARKET / OPENING / CROSS-INDEX RELATED COLUMNS")
    print("-" * 120)
    for c in hits:
        print(c)
        rows.append({"source": str(SRC), "column": c, "dtype": str(df[c].dtype)})

    print("\nKNOWN PRIOR-REGIME FIELDS")
    print("-" * 120)
    for c in [
        "market_prior_5d_consensus",
        "market_3idx_prior_5d_state",
        "relative_multi_horizon_state",
        "opening_2m_volume",
        "opening_participation_state",
    ]:
        print(f"{c}: {'YES' if c in df.columns else 'NO'}")

    pd.DataFrame(rows).drop_duplicates().to_csv(OUT, index=False)

    print("\n" + "=" * 120)
    print(f"Inventory CSV: {OUT}")
    print("RESULT: A41 EXISTING-EVIDENCE INVENTORY COMPLETE")
    print("No outcomes were analyzed.")
    print("No new market thresholds or states were created.")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
