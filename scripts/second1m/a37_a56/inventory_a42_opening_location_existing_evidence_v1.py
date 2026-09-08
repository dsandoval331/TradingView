from pathlib import Path
import pandas as pd

ROOT = Path("data/second1m_alt_entry_research_v1")
SOURCES = [
    ROOT/"ae2_c2_predictors_v1"/"ae2_c2_predictor_features_v1.parquet",
    ROOT/"ae2_session_levels_robustness_v1"/"ae2_session_levels_robustness_features_v1.parquet",
]
OUTDIR = ROOT/"ae2_opening_location_geometry_v1"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR/"a42_opening_location_existing_evidence_inventory_v1.csv"

TOKENS = [
    "gap","premarket","pre_market","pmh","pml","prior_rth","prior_close",
    "previous_close","overnight","ahh","ahl","afterhour","after_hour",
    "open","range","location","position","distance","pd"
]

def main():
    print("="*120)
    print("A42.1 - OPENING PRICE-LOCATION / OVERNIGHT GEOMETRY EXISTING-EVIDENCE INVENTORY")
    print("="*120)
    rows=[]
    for src in SOURCES:
        if not src.exists():
            print(f"\nMISSING: {src}")
            continue
        df=pd.read_parquet(src)
        print(f"\nSOURCE: {src}")
        print("-"*120)
        print(f"Rows: {len(df):,}  Columns: {len(df.columns):,}")
        hits=[c for c in df.columns if any(t in c.lower() for t in TOKENS)]
        for c in hits:
            print(c)
            rows.append({"source":str(src),"column":c,"dtype":str(df[c].dtype)})

        print("\nANCHOR AVAILABILITY")
        for c in [
            "c1_open","c1_close","c2_open","c2_close","entry_price",
            "prior_rth_close","pmh","pml","ahh","ahl","pdh","pdl",
            "gap_pct","gap_directional_pct","premarket_range_pct",
            "research_period","outcome"
        ]:
            print(f"{c}: {'YES' if c in df.columns else 'NO'}")

    pd.DataFrame(rows).drop_duplicates().to_csv(OUT,index=False)
    print("\n"+"="*120)
    print(f"Inventory CSV: {OUT}")
    print("RESULT: A42 EXISTING-EVIDENCE INVENTORY COMPLETE")
    print("No outcomes were analyzed.")
    print("No opening-location variables, thresholds, or states were created.")
    print("No Candidate Model V1 or prospective data was modified.")

if __name__=="__main__":
    main()
