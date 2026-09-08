from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path("data/second1m_alt_entry_research_v1")
BASE = ROOT / "ae2_session_levels_robustness_v1" / "ae2_session_levels_robustness_features_v1.parquet"
A41 = ROOT / "ae2_market_open_impulse_v1" / "a41_market_open_impulse_features_v1.parquet"

OUTDIR = ROOT / "ae2_opening_relative_strength_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / "a43_opening_relative_strength_existing_evidence_inventory_v1.csv"

TOKENS = [
    "c1_", "c2_", "body_return", "close_progress", "open_impulse",
    "spy", "qqq", "dia", "relative", "stock_vs", "directional_",
    "entry_timestamp", "research_period", "market_open"
]

def scan(src: Path, label: str):
    rows = []
    print(f"\nSOURCE: {label}")
    print("-" * 120)
    if not src.exists():
        print(f"MISSING: {src}")
        return rows

    df = pd.read_parquet(src)
    print(f"Path: {src}")
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns):,}")

    hits = [c for c in df.columns if any(t in c.lower() for t in TOKENS)]
    print("\nRELEVANT COLUMNS")
    for c in hits:
        print(c)
        rows.append({
            "source_label": label,
            "source": str(src),
            "column": c,
            "dtype": str(df[c].dtype),
        })

    return rows

def main():
    print("=" * 120)
    print("A43.1 - STOCK-vs-MARKET OPENING RELATIVE-STRENGTH EXISTING-EVIDENCE INVENTORY")
    print("=" * 120)

    rows = []
    rows += scan(BASE, "ENRICHED AE2 EVENTS")
    rows += scan(A41, "A41 MARKET-OPEN IMPULSE FEATURES")

    pd.DataFrame(rows).drop_duplicates().to_csv(OUT, index=False)

    print("\n" + "=" * 120)
    print(f"Inventory CSV: {OUT}")
    print("RESULT: A43 EXISTING-EVIDENCE INVENTORY COMPLETE")
    print("No outcomes were analyzed.")
    print("No relative-strength formulas, thresholds, or states were created.")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
