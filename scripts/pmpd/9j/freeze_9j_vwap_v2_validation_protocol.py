from pathlib import Path
import pandas as pd, json, hashlib, datetime

ROOT=Path.cwd()
D=ROOT/"pmpd_v5_9j_vwap_event_path_v2_analysis"/"discovery_stage1_restricted"
E=D/"discovery_evidence_summary"
OUT=ROOT/"pmpd_v5_9j_vwap_event_path_v2_analysis"/"frozen_validation_protocol"
OUT.mkdir(parents=True,exist_ok=True)

CUT=D/"discovery_unconditional_quantile_cutpoints.csv"
MAN=D/"discovery_stage1_manifest.json"
if not CUT.exists() or not MAN.exists(): raise SystemExit("DISCOVERY_ARTIFACT_MISSING")

cuts=pd.read_csv(CUT)
manifest=json.loads(MAN.read_text())

features=[
"directional_vwap_distance_min_from_dp1_pct",
"directional_vwap_distance_pct",
"event_minutes_since_last_cross",
"event_minutes_since_last_rejection",
"event_minutes_since_last_touch",
"event_vwap_touch_count_from_dp1",
]
scopes=["ALL","BULL","BEAR"]
frozen=cuts[cuts["feature"].isin(features)&cuts["scope"].isin(scopes)].copy()
if len(frozen)!=18:
    raise SystemExit(f"FREEZE_ROW_COUNT_FAIL expected=18 actual={len(frozen)}")
if frozen[["q25","q50","q75"]].isna().any().any():
    raise SystemExit("FREEZE_NULL_CUTPOINT_FAIL")

frozen["freeze_status"]="FROZEN_BEFORE_VALIDATION"
frozen["selection_basis"]="DISCOVERY_DESCRIPTIVE_NOT_OUTCOME_OPTIMIZED"
frozen.to_csv(OUT/"frozen_continuous_cutpoints.csv",index=False)

binary=pd.DataFrame([
 {"feature":"event_vwap_loss_after_dp4_full_stack_clearance",
  "scope":"ALL_AND_DIRECTION_SEPARATE",
  "comparison":"TRUE_VS_FALSE",
  "hypothesis":"VWAP loss after true DP4 full-stack clearance is associated with lower favorable-first rate.",
  "freeze_status":"FROZEN_BEFORE_VALIDATION",
  "selection_basis":"PRE_SPECIFIED_SEMANTIC_BINARY_STATE"},
 {"feature":"event_vwap_touch_from_dp1",
  "scope":"BULL_AND_BEAR_SEPARATE",
  "comparison":"TRUE_VS_FALSE",
  "hypothesis":"Event-specific VWAP touch from DP1 may have direction-dependent association; require directional replication rather than pooled effect.",
  "freeze_status":"FROZEN_BEFORE_VALIDATION",
  "selection_basis":"PRE_SPECIFIED_SEMANTIC_BINARY_STATE"},
 {"feature":"event_vwap_cross_from_dp1",
  "scope":"BULL_AND_BEAR_SEPARATE",
  "comparison":"TRUE_VS_FALSE",
  "hypothesis":"Event-specific VWAP cross from DP1 may have direction-dependent association; require directional replication rather than pooled effect.",
  "freeze_status":"FROZEN_BEFORE_VALIDATION",
  "selection_basis":"PRE_SPECIFIED_SEMANTIC_BINARY_STATE"},
])
binary.to_csv(OUT/"frozen_binary_hypotheses.csv",index=False)

protocol={
 "experiment":"PMPD_V5_9J_VWAP_EVENT_PATH_V2",
 "protocol_version":"PMPD_V5_9J_VWAP_EVENT_PATH_V2_VALIDATION_FREEZE_V1",
 "freeze_date_utc":"2026-09-07",
 "discovery_rows":145692,
 "validation_a_rows":147486,
 "validation_b_rows":157313,
 "validation_outcomes_characterized_before_freeze":False,
 "primary_outcome":"FAVORABLE_FIRST vs ADVERSE_FIRST; unresolved and ambiguous_same_bar excluded from resolved-rate denominator but reported",
 "continuous_features":features,
 "continuous_scopes":scopes,
 "continuous_cutpoints":"Exact unconditional Discovery Q25/Q50/Q75 values in frozen_continuous_cutpoints.csv; no re-estimation in validation.",
 "binary_hypotheses_file":"frozen_binary_hypotheses.csv",
 "minimum_scope_n":200,
 "validation_requirements":[
   "Evaluate VALIDATION_A and VALIDATION_B separately.",
   "Evaluate BULL and BEAR separately; pooled results are supplementary.",
   "Do not alter cutpoints after observing validation.",
   "Require direction and temporal robustness for SUPPORTED status.",
   "Assess symbol-cluster robustness; broad cross-symbol support is required.",
   "Discovery effect size is descriptive and not evidence of validation success.",
   "No Pine production rule is authorized by this freeze."
 ],
 "adjudication":{
   "SUPPORTED":"Replicates materially in both validation periods with directionally coherent evidence and acceptable symbol-cluster robustness.",
   "CONDITIONAL":"Some replication but temporal, directional, or symbol-cluster dependence prevents general production use.",
   "NOT_SUPPORTED":"Fails to replicate, reverses materially, or is too weak/unstable."
 },
 "excluded_from_validation_rule_search":[
   "rth_vwap_at_decision",
   "event_vwap_loss_after_first_dp345_legacy",
   "vwap_event_path_version",
   "vwap_event_path_derivation_version"
 ]
}
(OUT/"frozen_validation_protocol.json").write_text(json.dumps(protocol,indent=2),encoding="utf-8")

h=hashlib.sha256()
for fn in ["frozen_continuous_cutpoints.csv","frozen_binary_hypotheses.csv","frozen_validation_protocol.json"]:
    h.update((OUT/fn).read_bytes())
fp=h.hexdigest()
(OUT/"FREEZE_FINGERPRINT.txt").write_text(fp+"\n",encoding="utf-8")

print("FROZEN_CONTINUOUS_ROWS =",len(frozen))
print(frozen[["feature","scope","q25","q50","q75"]].to_string(index=False))
print("\nFROZEN_BINARY_HYPOTHESES =",len(binary))
print(binary[["feature","scope","comparison"]].to_string(index=False))
print("\nFREEZE_FINGERPRINT =",fp)
print("PRE_VALIDATION_FREEZE_GATE=PASS")
print("VALIDATION_OUTCOMES_CHARACTERIZED_BEFORE_FREEZE=False")
print("CUTPOINT_REESTIMATION_IN_VALIDATION_ALLOWED=False")
print("9K_OPENED=False")
