from pathlib import Path
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
SOURCES=[
 ("ENRICHED AE2 EVENTS", ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"),
 ("PREMARKET CONTEXT", ROOT/"ae2_premarket_context_v1"/"ae2_premarket_context_features_v1.parquet"),
]
OUTDIR=ROOT/"ae2_premarket_shape_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a46_premarket_shape_existing_evidence_inventory_v1.csv"

TOKENS=["pre_","premarket","pmh","pml","volume","bar_n","range","close_location"]

def main():
    print("="*120)
    print("A46.1 - PREMARKET SHAPE / INTERNAL STRUCTURE EXISTING-EVIDENCE INVENTORY")
    print("="*120)
    rows=[]
    for label,src in SOURCES:
        print(f"\nSOURCE: {label}\n"+"-"*120)
        if not src.exists():
            print(f"MISSING: {src}"); continue
        x=pd.read_parquet(src)
        print(f"Path: {src}")
        print(f"Rows: {len(x):,}  Columns: {len(x.columns):,}")
        print("\nRELEVANT COLUMNS")
        for c in x.columns:
            if any(t in c.lower() for t in TOKENS):
                print(c)
                rows.append({"source_label":label,"source":str(src),"column":c,"dtype":str(x[c].dtype)})
        print("\nANCHOR CHECK")
        for c in ["pre_open","pre_high","pre_low","pre_close","pre_last_close",
                  "pmh","pml","premarket_range_pct","premarket_close_location_pct",
                  "directional_premarket_close_location_pct","research_period","outcome"]:
            print(f"{c}: {'YES' if c in x.columns else 'NO'}")
    pd.DataFrame(rows).drop_duplicates().to_csv(OUT,index=False)
    print(f"\nInventory CSV: {OUT}")
    print("RESULT: A46 EXISTING-EVIDENCE INVENTORY COMPLETE")
    print("No outcomes analyzed. No new premarket-shape variables or thresholds created.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
