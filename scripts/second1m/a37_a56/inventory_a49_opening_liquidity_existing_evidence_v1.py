from pathlib import Path
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
SRC=ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet"
OUTDIR=ROOT/"ae2_opening_liquidity_v1"; OUTDIR.mkdir(parents=True,exist_ok=True)
OUT=OUTDIR/"a49_opening_liquidity_existing_evidence_inventory_v1.csv"

TOKENS=["dollar","notional","liquidity","turnover","share","volume","price","spread","atr","range_pct","market_cap"]

def main():
    print("="*120)
    print("A49.1 - OPENING LIQUIDITY / DOLLAR-ACTIVITY EXISTING-EVIDENCE INVENTORY")
    print("="*120)
    x=pd.read_parquet(SRC)
    print(f"Source: {SRC}\nRows: {len(x):,}  Columns: {len(x.columns):,}")
    rows=[]
    print("\nRELEVANT COLUMNS")
    for c in x.columns:
        if any(t in c.lower() for t in TOKENS):
            print(c)
            rows.append({"source":str(SRC),"column":c,"dtype":str(x[c].dtype)})
    print("\nANCHOR CHECK")
    for c in ["c1_volume","c2_volume","opening_2m_volume","entry_price","c2_close",
              "opening_2m_volume_median_20d_prior","opening_2m_rvol_20d",
              "research_period","outcome"]:
        print(f"{c}: {'YES' if c in x.columns else 'NO'}")
    pd.DataFrame(rows).to_csv(OUT,index=False)
    print(f"\nInventory CSV: {OUT}")
    print("RESULT: A49 EXISTING-EVIDENCE INVENTORY COMPLETE")
    print("No outcomes analyzed. No liquidity variables or thresholds created.")
    print("No Candidate Model V1 or prospective data modified.")
if __name__=="__main__": main()
