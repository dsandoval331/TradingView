from pathlib import Path
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
SRC=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
OUTDIR=ROOT/"ae2_prior_day_vs_premarket_transition_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a45_existing_evidence_inventory_v1.csv"

TOKENS=["prior_rth_close","prior_ah_close","pre_last_close","pre_open","pre_close",
        "premarket_close","premarket_gap","rth_open_gap","directional_premarket",
        "ahh","ahl","pmh","pml","gap_premarket","prior_session_date"]

def main():
    print("="*120)
    print("A45.1 - PRIOR-DAY -> AFTER-HOURS -> PREMARKET TRANSITION EXISTING-EVIDENCE INVENTORY")
    print("="*120)
    if not SRC.exists():
        raise FileNotFoundError(SRC)
    x=pd.read_parquet(SRC)
    print(f"Source: {SRC}")
    print(f"Rows: {len(x):,}  Columns: {len(x.columns):,}")
    rows=[]
    print("\nRELEVANT COLUMNS")
    for c in x.columns:
        if any(t in c.lower() for t in TOKENS):
            print(c)
            rows.append({"source":str(SRC),"column":c,"dtype":str(x[c].dtype)})
    print("\nANCHOR CHECK")
    anchors=["prior_rth_close","prior_ah_close","pre_last_close","ahh","ahl","pmh","pml",
             "directional_gap_from_prior_close_pct","research_period","outcome"]
    for c in anchors:
        print(f"{c}: {'YES' if c in x.columns else 'NO'}")
    pd.DataFrame(rows).to_csv(OUT,index=False)
    print(f"\nInventory CSV: {OUT}")
    print("RESULT: A45 EXISTING-EVIDENCE INVENTORY COMPLETE")
    print("No outcomes analyzed. No transition variables or thresholds created.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
