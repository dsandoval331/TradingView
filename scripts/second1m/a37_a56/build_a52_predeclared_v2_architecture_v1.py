from pathlib import Path
import json, hashlib
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
D=ROOT/"ae2_v2_evidence_consolidation_v1"
M=D/"a51_retained_v2_evidence_matrix_5FACTOR_CERTIFIED_v1.parquet"
OUT=ROOT/"ae2_v2_model_architecture_v1"
OUT.mkdir(parents=True,exist_ok=True)

POS=[
"A37_G_P2_PD_AH_PM_ORDERING",
"A38_T_P1_PM_REMAINS_FOR_C2",
]
NEG=[
"A37_G_N1_PM_PD_SPACING_Q4",
"A38_T_N1_PD_REMAINS_FOR_C2",
"A42_N2_OPEN_CONSUMED_RATIO_Q2",
]

SPEC={
"architecture_id":"ALT_C2_V2_PREDECLARED_ARCHITECTURE_V1",
"purpose":"Freeze an outcome-blind V2 evidence-combination architecture before any combined outcome evaluation.",
"base_population":"753 historical Candidate-V1 Preferred binary events in A51 five-factor certified matrix.",
"positive_evidence":POS,
"negative_evidence":NEG,
"a39_status":"EXCLUDED_PROVENANCE_CONFLICTED",
"combination_rule":{
  "positive_present":"OR across the two positive candidates",
  "negative_present":"OR across the three negative candidates",
  "state_priority":"No priority/override. Positive and negative evidence are represented separately.",
  "states":{
    "UPGRADE":"positive_present AND NOT negative_present",
    "DOWNGRADE":"negative_present AND NOT positive_present",
    "CONFLICT":"positive_present AND negative_present",
    "BASE":"NOT positive_present AND NOT negative_present"
  }
},
"intensity_fields":{
  "positive_count":"0..2, descriptive only",
  "negative_count":"0..3, descriptive only",
  "total_evidence_count":"positive_count + negative_count, descriptive only"
},
"predeclared_constraints":[
  "No outcome information is used to define states.",
  "No weights are fitted.",
  "No candidate threshold is changed.",
  "No pairwise interaction is promoted into a rule.",
  "A38_T_N1 and A42_N2 remain separate evidence flags despite moderate overlap; OR only determines negative_present.",
  "CONFLICT is preserved as its own state rather than resolved post hoc.",
  "Candidate Model V1 and prospective V1 remain unchanged.",
  "A52 state definitions must be frozen before outcome evaluation."
]
}

def main():
    x=pd.read_parquet(M)
    assert len(x)==753 and "outcome" not in x.columns
    missing=[c for c in POS+NEG if c not in x.columns]
    if missing: raise KeyError(missing)

    x["a52_positive_count"]=x[POS].astype(int).sum(axis=1)
    x["a52_negative_count"]=x[NEG].astype(int).sum(axis=1)
    x["a52_total_evidence_count"]=x["a52_positive_count"]+x["a52_negative_count"]
    x["a52_positive_present"]=x["a52_positive_count"].gt(0)
    x["a52_negative_present"]=x["a52_negative_count"].gt(0)

    def state(r):
        p,n=r["a52_positive_present"],r["a52_negative_present"]
        if p and not n: return "UPGRADE"
        if n and not p: return "DOWNGRADE"
        if p and n: return "CONFLICT"
        return "BASE"
    x["a52_state"]=x.apply(state,axis=1)

    # Outcome-free descriptive state distribution.
    rows=[]
    for period,z in [("ALL",x),("DISCOVERY",x[x.research_period.eq("DISCOVERY")]),("VALIDATION",x[x.research_period.eq("VALIDATION")])]:
        for s,n in z.a52_state.value_counts().items():
            rows.append({"period":period,"state":s,"n":int(n),"pct":100*n/len(z)})
    dist=pd.DataFrame(rows).sort_values(["period","state"])
    dist.to_csv(OUT/"a52_state_distribution_outcome_free_v1.csv",index=False)

    # Freeze spec with hash.
    canonical=json.dumps(SPEC,sort_keys=True,separators=(",",":"))
    SPEC["sha256"]=hashlib.sha256(canonical.encode()).hexdigest()
    (OUT/"ALT_C2_V2_PREDECLARED_ARCHITECTURE_V1.json").write_text(json.dumps(SPEC,indent=2),encoding="utf-8")

    # Save outcome-free state matrix for later outcome join only after freeze.
    x.to_parquet(OUT/"a52_v2_state_matrix_OUTCOME_FREE_v1.parquet",index=False)
    x.to_csv(OUT/"a52_v2_state_matrix_OUTCOME_FREE_v1.csv",index=False)

    print("="*132)
    print("A52 - PREDECLARED V2 MODEL ARCHITECTURE FREEZE (OUTCOME-BLIND)")
    print("="*132)
    print("Population:",len(x))
    print("\nPositive evidence:")
    for c in POS: print(" +",c)
    print("Negative evidence:")
    for c in NEG: print(" -",c)
    print("\nFrozen states: UPGRADE / DOWNGRADE / CONFLICT / BASE")
    print("\nOUTCOME-FREE STATE DISTRIBUTION")
    print(dist.to_string(index=False,float_format=lambda v:f"{v:.2f}"))
    print("\nPositive-count distribution:")
    print(x.a52_positive_count.value_counts().sort_index().to_string())
    print("\nNegative-count distribution:")
    print(x.a52_negative_count.value_counts().sort_index().to_string())
    print("\nSpec SHA256:",SPEC["sha256"])
    print("Spec:",OUT/"ALT_C2_V2_PREDECLARED_ARCHITECTURE_V1.json")
    print("State matrix:",OUT/"a52_v2_state_matrix_OUTCOME_FREE_v1.parquet")
    print("\nRESULT: A52 ARCHITECTURE FROZEN WITHOUT OUTCOME ANALYSIS.")
    print("No prospective data used. Candidate Model V1 unchanged.")

if __name__=="__main__": main()
