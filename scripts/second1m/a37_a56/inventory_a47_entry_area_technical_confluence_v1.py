from pathlib import Path
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
SRC=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
OUTDIR=ROOT/"ae2_level_confluence_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a47_level_confluence_existing_evidence_inventory_v1.csv"

TOKENS=["ema9","ema20","sma20","vwap","pmh","pml","pdh","pdl","ahh","ahl",
        "directional_level","distance_pct","session_level","cluster","entry_price","c2_close"]

def main():
    print("="*120)
    print("A47.1 - ENTRY-AREA TECHNICAL CONFLUENCE EXISTING-EVIDENCE INVENTORY")
    print("="*120)
    if not SRC.exists(): raise FileNotFoundError(SRC)
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
    for c in ["entry_price","c2_close","c2_vwap","ema9","ema20","sma20",
              "pm_directional_level","ah_directional_level","pd_directional_level",
              "pm_directional_distance_pct","ah_directional_distance_pct","pd_directional_distance_pct",
              "research_period","outcome"]:
        print(f"{c}: {'YES' if c in x.columns else 'NO'}")
    pd.DataFrame(rows).to_csv(OUT,index=False)
    print(f"\nInventory CSV: {OUT}")
    print("RESULT: A47 EXISTING-EVIDENCE INVENTORY COMPLETE")
    print("No outcomes analyzed. No confluence distances, thresholds, or states created.")
    print("No Candidate Model V1 or prospective data modified.")

if __name__=="__main__": main()
