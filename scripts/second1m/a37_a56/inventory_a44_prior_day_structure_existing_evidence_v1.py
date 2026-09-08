from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path("data/second1m_alt_entry_research_v1")
SOURCES = [
    ("ENRICHED AE2 EVENTS", ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"),
    ("PREMARKET CONTEXT", ROOT/"ae2_premarket_context_v1"/"ae2_premarket_context_features_v1.parquet"),
]

TOKENS = [
    "prior_", "previous_", "pdh", "pdl", "prior_rth", "range", "close",
    "open", "body", "clv", "wick", "daily", "gap"
]

OUTDIR = ROOT/"ae2_prior_day_structure_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR/"a44_prior_day_structure_existing_evidence_inventory_v1.csv"

def main():
    print("="*120)
    print("A44.1 - PRIOR-DAY SESSION STRUCTURE EXISTING-EVIDENCE INVENTORY")
    print("="*120)
    rows=[]
    for label,src in SOURCES:
        print(f"\nSOURCE: {label}")
        print("-"*120)
        if not src.exists():
            print(f"MISSING: {src}")
            continue
        df=pd.read_parquet(src)
        print(f"Path: {src}")
        print(f"Rows: {len(df):,}  Columns: {len(df.columns):,}")
        hits=[c for c in df.columns if any(t in c.lower() for t in TOKENS)]
        for c in hits:
            print(c)
            rows.append({"source_label":label,"source":str(src),"column":c,"dtype":str(df[c].dtype)})

        print("\nANCHOR CHECK")
        for c in [
            "prior_rth_close","prior_close","pdh","pdl",
            "prior_open","prior_high","prior_low",
            "prior_range_pct","prior_close_location_pct",
            "research_period","outcome"
        ]:
            print(f"{c}: {'YES' if c in df.columns else 'NO'}")

    pd.DataFrame(rows).drop_duplicates().to_csv(OUT,index=False)
    print("\n"+"="*120)
    print(f"Inventory CSV: {OUT}")
    print("RESULT: A44 EXISTING-EVIDENCE INVENTORY COMPLETE")
    print("No outcomes were analyzed.")
    print("No prior-day structure variables, thresholds, or states were created.")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__=="__main__":
    main()
