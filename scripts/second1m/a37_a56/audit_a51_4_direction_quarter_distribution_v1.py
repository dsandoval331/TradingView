from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path("data/second1m_alt_entry_research_v1")
D=ROOT/"ae2_v2_evidence_consolidation_v1"
M=D/"a51_retained_v2_evidence_matrix_5FACTOR_CERTIFIED_v1.parquet"
OUT=D/"a51_4_direction_quarter_distribution_audit_v1.csv"

CANDS=[
"A37_G_N1_PM_PD_SPACING_Q4",
"A37_G_P2_PD_AH_PM_ORDERING",
"A38_T_P1_PM_REMAINS_FOR_C2",
"A38_T_N1_PD_REMAINS_FOR_C2",
"A42_N2_OPEN_CONSUMED_RATIO_Q2",
]

def main():
    x=pd.read_parquet(M)
    assert len(x)==753
    assert "outcome" not in x.columns
    rows=[]
    for c in CANDS:
        for dim in ["direction","quarter","research_period"]:
            for val,z in x.groupby(dim,dropna=False):
                rows.append({
                    "candidate":c,"dimension":dim.upper(),"value":str(val),
                    "population_n":len(z),"fires":int(z[c].sum()),
                    "prevalence_pct":100*z[c].mean()
                })
    out=pd.DataFrame(rows)
    out.to_csv(OUT,index=False)

    print("="*132)
    print("A51.4B - DIRECTION / QUARTER / PERIOD DISTRIBUTION AUDIT (OUTCOME-FREE)")
    print("="*132)
    for c in CANDS:
        print("\n"+c)
        print("-"*100)
        z=out[out.candidate.eq(c)]
        for dim in ["DIRECTION","QUARTER","RESEARCH_PERIOD"]:
            print("\n"+dim)
            print(z[z.dimension.eq(dim)][["value","population_n","fires","prevalence_pct"]]
                  .to_string(index=False,float_format=lambda v:f"{v:.2f}"))
    print("\nAudit CSV:",OUT)
    print("RESULT: A51.4B COMPLETE.")
    print("No outcomes analyzed. No prospective data used. No combinations optimized.")

if __name__=="__main__": main()
