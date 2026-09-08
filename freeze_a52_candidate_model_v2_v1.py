from pathlib import Path
import json, hashlib
import pandas as pd

ROOT=Path("data/second1m_alt_entry_research_v1")
A52=ROOT/"ae2_v2_model_architecture_v1"
SPEC=A52/"ALT_C2_V2_PREDECLARED_ARCHITECTURE_V1.json"
STATE=A52/"a52_v2_state_matrix_OUTCOME_FREE_v1.parquet"
OUT=A52/"ALT_C2_CANDIDATE_MODEL_V2.json"

def main():
    spec=json.loads(SPEC.read_text(encoding="utf-8"))
    x=pd.read_parquet(STATE)
    assert len(x)==753 and "outcome" not in x.columns
    counts=x["a52_state"].value_counts().to_dict()

    model={
      "candidate_model_id":"ALT_C2_CANDIDATE_MODEL_V2",
      "status":"FROZEN_HISTORICAL_CANDIDATE_PENDING_INDEPENDENT_PROSPECTIVE_VALIDATION",
      "parent_model":"ALT_C2_CANDIDATE_MODEL_V1",
      "scope":"Refinement layer applied only inside Candidate-V1 PREFERRED events.",
      "architecture_id":spec["architecture_id"],
      "architecture_spec_sha256":spec["sha256"],
      "positive_evidence":spec["positive_evidence"],
      "negative_evidence":spec["negative_evidence"],
      "excluded_evidence":{
        "A39_T_V1_VWAP_EXPANSION_Q3":"PROVENANCE_CONFLICTED_NON_RECONSTRUCTIBLE"
      },
      "state_definitions":spec["combination_rule"]["states"],
      "state_semantics":{
        "UPGRADE":"higher-confidence V1 Preferred subset",
        "BASE":"V1 Preferred with no retained V2 evidence",
        "DOWNGRADE":"V1 Preferred with negative V2 evidence and no positive V2 evidence",
        "CONFLICT":"V1 Preferred with both positive and negative V2 evidence; preserve separately"
      },
      "historical_population_n":len(x),
      "outcome_free_state_counts":{k:int(v) for k,v in counts.items()},
      "research_constraints":[
        "No weights fitted.",
        "No thresholds changed after combined outcomes were viewed.",
        "No conflict reassignment.",
        "Quarter failures 2025Q3 and 2026Q1 are preserved and not optimized away.",
        "Candidate Model V1 and its prospective validation remain unchanged.",
        "V2 is not production/prospective-approved until a separate prospective protocol is frozen and completed."
      ]
    }
    canonical=json.dumps(model,sort_keys=True,separators=(",",":"))
    model["sha256"]=hashlib.sha256(canonical.encode()).hexdigest()
    OUT.write_text(json.dumps(model,indent=2),encoding="utf-8")

    print("="*132)
    print("A52.4 - CANDIDATE MODEL V2 FREEZE")
    print("="*132)
    print("Model:",model["candidate_model_id"])
    print("Status:",model["status"])
    print("Parent:",model["parent_model"])
    print("Architecture hash:",model["architecture_spec_sha256"])
    print("Model hash:",model["sha256"])
    print("Historical population:",model["historical_population_n"])
    print("Outcome-free state counts:",model["outcome_free_state_counts"])
    print("\nPreserved cautions:")
    for s in model["research_constraints"]: print(" -",s)
    print("\nOutput:",OUT)
    print("RESULT: CANDIDATE MODEL V2 FROZEN. NO PROSPECTIVE DATA USED OR MODIFIED.")

if __name__=="__main__": main()
