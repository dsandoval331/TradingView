from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path("data/second1m_alt_entry_research_v1")
OUTDIR = ROOT / "ae2_c1_c2_transition_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / "a39_a37_source_inventory_v1.csv"

TOKENS = [
    "mean_pairwise_spacing",
    "pm_pd_spacing",
    "order",
    "pd_ah_pm",
    "compact",
    "geometry",
]

def main():
    rows = []
    print("=" * 120)
    print("A39.6A - A37 FROZEN GEOMETRY SOURCE INVENTORY")
    print("=" * 120)

    for p in sorted(ROOT.rglob("*.parquet")):
        try:
            cols = pd.read_parquet(p).columns.tolist()
        except Exception:
            continue

        hits = [c for c in cols if any(t in c.lower() for t in TOKENS)]
        if hits:
            print(f"\nSOURCE: {p}")
            print("-" * 120)
            for c in hits:
                print(c)
                rows.append({"source": str(p), "column": c})

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"\nInventory CSV: {OUT}")

    if not rows:
        print("RESULT: NO A37 GEOMETRY PARQUET COLUMNS LOCATED")
    else:
        print("RESULT: A37 GEOMETRY SOURCE INVENTORY COMPLETE")

    print("No outcomes were analyzed. No thresholds were recomputed.")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__ == "__main__":
    main()
