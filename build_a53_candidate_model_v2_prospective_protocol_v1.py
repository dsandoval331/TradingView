from pathlib import Path
import json, hashlib

ROOT=Path("data/second1m_alt_entry_research_v1")
V2=ROOT/"ae2_v2_model_architecture_v1"/"ALT_C2_CANDIDATE_MODEL_V2.json"
PROOT=Path("data/second1m_alt_entry_prospective_v2")
PDIR=PROOT/"protocol"
PDIR.mkdir(parents=True,exist_ok=True)
OUT=PDIR/"ALT_C2_PROSPECTIVE_VALIDATION_V2.json"

def main():
    model=json.loads(V2.read_text(encoding="utf-8"))
    assert model["candidate_model_id"]=="ALT_C2_CANDIDATE_MODEL_V2"
    assert model["status"]=="FROZEN_HISTORICAL_CANDIDATE_PENDING_INDEPENDENT_PROSPECTIVE_VALIDATION"

    protocol={
      "protocol_id":"ALT_C2_PROSPECTIVE_VALIDATION_V2",
      "candidate_model_id":"ALT_C2_CANDIDATE_MODEL_V2",
      "parent_model_id":"ALT_C2_CANDIDATE_MODEL_V1",
      "model_sha256":model["sha256"],
      "architecture_spec_sha256":model["architecture_spec_sha256"],
      "status":"FROZEN_BEFORE_V2_PROSPECTIVE_OUTCOME_EVALUATION",
      "historical_research_end_date":"2026-08-27",
      "prospective_start_date":"2026-08-28",
      "cohort_rule":"Score V2 only on events classified PREFERRED by frozen Candidate Model V1.",
      "important_independence_note":"V2 was developed using historical data ending 2026-08-27. Existing post-2026-08-27 V1 prospective events may be scored by frozen V2 only after this protocol freeze; no V2 rule may be changed using those outcomes.",
      "primary_outcome":{
        "definition":"+0.50% favorable before -0.50% adverse",
        "binary_population":["FAVORABLE_FIRST","ADVERSE_FIRST"],
        "track_separately":["BOTH_SAME_BAR","UNRESOLVED"]
      },
      "states":["UPGRADE","BASE","CONFLICT","DOWNGRADE"],
      "primary_hypotheses":[
        "UPGRADE > BASE > DOWNGRADE in binary favorable-first rate.",
        "UPGRADE - DOWNGRADE spread >= 7 percentage points.",
        "UPGRADE favorable-first rate >= 60%.",
        "DOWNGRADE favorable-first rate <= 53%."
      ],
      "directional_confirmation":{
        "rule":"For BULL and BEAR separately, UPGRADE > DOWNGRADE once both state-direction cells meet minimum N.",
        "minimum_n_per_state_direction":40
      },
      "minimum_binary_samples":{
        "UPGRADE":100,
        "BASE":200,
        "DOWNGRADE":150,
        "CONFLICT":60
      },
      "review_checkpoints":{
        "UPGRADE":[25,50,100],
        "DOWNGRADE":[50,100,150],
        "policy":"Descriptive review only. No early stopping and no model changes."
      },
      "concentration_checks":{
        "max_single_symbol_share_of_upgrade_pct":7.5,
        "max_top10_symbol_share_of_upgrade_pct":45.0,
        "note":"Higher than V1 thresholds because V2 UPGRADE is a smaller nested cohort; failures are cautions, not automatic model edits."
      },
      "frozen_rules":{
        "positive_evidence":model["positive_evidence"],
        "negative_evidence":model["negative_evidence"],
        "state_definitions":model["state_definitions"],
        "conflict_policy":"Preserve CONFLICT as separate state; no reassignment.",
        "a39":"Excluded permanently from this V2 protocol because provenance-conflicted/non-reconstructible."
      },
      "research_firewall":[
        "Candidate Model V1 prospective validation remains unchanged.",
        "V2 scoring must not modify the V1 ledger or V1 classifications.",
        "No V2 thresholds, weights, candidate membership, or state definitions may change during this protocol.",
        "No outcome-optimized subgroups may be created from prospective V2 events.",
        "2025Q3 and 2026Q1 historical failures remain part of the record and are not filtered out.",
        "Any model change freezes this protocol and requires a separately named V3 or successor protocol."
      ]
    }

    canonical=json.dumps(protocol,sort_keys=True,separators=(",",":"))
    protocol["sha256"]=hashlib.sha256(canonical.encode()).hexdigest()
    OUT.write_text(json.dumps(protocol,indent=2),encoding="utf-8")

    print("="*136)
    print("A53.1 - CANDIDATE MODEL V2 PROSPECTIVE VALIDATION PROTOCOL FREEZE")
    print("="*136)
    print("Protocol:",protocol["protocol_id"])
    print("Candidate:",protocol["candidate_model_id"])
    print("Model hash:",protocol["model_sha256"])
    print("Architecture hash:",protocol["architecture_spec_sha256"])
    print("Protocol hash:",protocol["sha256"])
    print("Historical research end:",protocol["historical_research_end_date"])
    print("Prospective start:",protocol["prospective_start_date"])
    print("\nCohort:",protocol["cohort_rule"])
    print("\nMinimum binary samples:",protocol["minimum_binary_samples"])
    print("Directional minimum:",protocol["directional_confirmation"]["minimum_n_per_state_direction"])
    print("\nPrimary hypotheses:")
    for h in protocol["primary_hypotheses"]: print(" -",h)
    print("\nFirewall:")
    for h in protocol["research_firewall"]: print(" -",h)
    print("\nOutput:",OUT)
    print("RESULT: A53.1 V2 PROSPECTIVE PROTOCOL FROZEN.")
    print("No prospective outcomes read. V1 prospective protocol and ledger untouched.")

if __name__=="__main__": main()
