from pathlib import Path
import pandas as pd

LED=Path("data/second1m_alt_entry_prospective_v1/events/altc2_prospective_event_ledger_v1.parquet")
TOKENS=("c1_","c2_","pm_","ah_","pd_","directional_level","level_structure","entry_","candidate")

def main():
    x=pd.read_parquet(LED)
    print("="*136)
    print("A53.2B - C1 LEVEL-TIMING RECONSTRUCTION INVENTORY")
    print("="*136)
    print("Rows:",len(x),"Columns:",len(x.columns))
    print("\nRelevant ledger columns:")
    for c in x.columns:
        if any(t in c.lower() for t in TOKENS):
            print(c)

    wanted=[
      "symbol","trade_date","direction","combined_candidate_state","candidate_triage_state",
      "candidate_model_id","c1_open","c1_high","c1_low","c1_close",
      "c2_open","c2_high","c2_low","c2_close",
      "pm_directional_level","ah_directional_level","pd_directional_level",
      "pm_c1_cross","ah_c1_cross","pd_c1_cross",
      "pm_c2_cross","ah_c2_cross","pd_c2_cross",
      "pm_c2_closed_beyond","ah_c2_closed_beyond","pd_c2_closed_beyond"
    ]
    print("\nExact wanted-field availability:")
    for c in wanted:
        print(f"{c:36s} {'YES' if c in x.columns else 'NO'}")

    # Show categorical values only; deliberately do not print outcome.
    for c in ["combined_candidate_state","candidate_triage_state","candidate_model_id",
              "pm_c1_cross","ah_c1_cross","pd_c1_cross"]:
        if c in x.columns:
            print(f"\n{c} value counts:")
            print(x[c].value_counts(dropna=False).to_string())

    print("\nRESULT: A53.2B INVENTORY COMPLETE.")
    print("No outcomes printed or analyzed. No V2 scoring performed.")

if __name__=="__main__": main()
