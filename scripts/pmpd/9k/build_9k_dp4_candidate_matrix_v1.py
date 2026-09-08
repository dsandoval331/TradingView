from pathlib import Path
import json, hashlib
import pandas as pd
ROOT=Path.cwd()
BASE=ROOT/"pmpd_v5_9h_research_dataset_v1"/"decision_research.csv"
ENR=ROOT/"pmpd_v5_9h_enrichment_v1"/"decision_enrichment.csv"
VW=ROOT/"pmpd_v5_9j_vwap_event_path_v2_analysis"/"decision_vwap_event_path_v2_dp4fix_with_frozen_outcome.csv"
OUT=ROOT/"pmpd_v5_9k_dp4_candidate_matrix_v1"
OUT.mkdir(exist_ok=True)

print("=== PMPD V5 9K DP4 CANDIDATE MATRIX V1 ===")
b=pd.read_csv(BASE,low_memory=False)
e=pd.read_csv(ENR,low_memory=False)
v=pd.read_csv(VW,low_memory=False)

# Exact frozen anchor and primary-unit eligibility.
m=(b["decision_type"].astype(str)=="DP4_FULL_STACK_FIRST_CLEAR")
d=b.loc[m].copy()
if "primary_decision_unit" in d:
    d=d[d["primary_decision_unit"].astype(str).str.lower().eq("true")].copy()
if "primary_inference_eligible" in d:
    d=d[d["primary_inference_eligible"].astype(str).str.lower().eq("true")].copy()

print("DP4_ELIGIBLE_ROWS =",len(d))
print("DP4_UNIQUE_DECISIONS =",d["decision_id"].nunique())

# Entry-known structural candidates. No outcome-derived transformations.
base_cols=["decision_id","event_id","symbol","direction","timestamp_utc","decision_type",
           "six_level_scale_ratio","overnight_gap_pct"]
base_cols=[c for c in base_cols if c in d.columns]
x=d[base_cols].copy()

# Direction-normalized overnight gap, definition frozen in 9H.
sgn=x["direction"].astype(str).str.upper().map({"BULL":1.0,"BEAR":-1.0})
x["direction_normalized_overnight_gap_pct"]=x["overnight_gap_pct"]*sgn

# Time-of-day representation: minutes from 09:30 America/New_York.
ts=pd.to_datetime(x["timestamp_utc"],utc=True)
ny=ts.dt.tz_convert("America/New_York")
x["decision_minutes_from_rth_open"]=(ny.dt.hour*60+ny.dt.minute)-(9*60+30)

# Join exact DP4 VWAP decision-time state only.
vw_cols=["decision_id","research_partition","frozen_primary_outcome",
         "directional_vwap_distance_pct","directional_vwap_distance_min_from_dp1_pct",
         "directional_vwap_distance_max_from_dp1_pct","directional_vwap_side",
         "event_minutes_from_dp1","event_vwap_touch_from_dp1",
         "event_vwap_touch_count_from_dp1","event_vwap_cross_from_dp1",
         "event_vwap_cross_count_from_dp1","event_directional_rejection_seen",
         "event_directional_rejection_count","event_minutes_since_last_touch",
         "event_minutes_since_last_cross","event_minutes_since_last_rejection",
         "event_vwap_side_changed_from_dp1"]
vw_cols=[c for c in vw_cols if c in v.columns]
x=x.merge(v[vw_cols],on="decision_id",how="left",validate="one_to_one")

# Explicitly prohibit post-DP4 and legacy path fields.
prohibited=[
 "event_vwap_loss_after_dp4_full_stack_clearance",
 "event_vwap_loss_after_first_dp345_legacy",
 "event_minutes_since_last_loss","event_minutes_since_last_reclaim",
 "dp4_full_stack_first_clear_timestamp_utc","event_last_vwap_loss_timestamp_utc"
]
hits=[c for c in prohibited if c in x.columns]

# Integrity.
assert x["decision_id"].is_unique
assert len(x)==len(d)
assert not hits, hits
assert x["research_partition"].notna().all()
assert x["frozen_primary_outcome"].notna().all()

# Candidate groups are preregistered, not selected by current outcomes.
groups={
 "CORE_9H_CONDITIONAL":[
   "six_level_scale_ratio","direction_normalized_overnight_gap_pct","decision_minutes_from_rth_open"
 ],
 "VWAP_DP4_CONTEXT_CONTINUOUS":[
   "directional_vwap_distance_pct","directional_vwap_distance_min_from_dp1_pct",
   "directional_vwap_distance_max_from_dp1_pct","event_minutes_from_dp1",
   "event_vwap_touch_count_from_dp1","event_vwap_cross_count_from_dp1",
   "event_directional_rejection_count","event_minutes_since_last_touch",
   "event_minutes_since_last_cross","event_minutes_since_last_rejection"
 ],
 "VWAP_DP4_CONTEXT_BINARY":[
   "event_vwap_touch_from_dp1","event_vwap_cross_from_dp1",
   "event_directional_rejection_seen","event_vwap_side_changed_from_dp1"
 ],
 "CONTEXT_ONLY_CATEGORICAL":["directional_vwap_side"]
}
groups={k:[c for c in vv if c in x.columns] for k,vv in groups.items()}

# Missingness only; no outcome association.
missing={c:int(x[c].isna().sum()) for vv in groups.values() for c in vv}
part_counts=x["research_partition"].value_counts(dropna=False).to_dict()
dir_counts=x["direction"].value_counts(dropna=False).to_dict()
out_counts=x["frozen_primary_outcome"].value_counts(dropna=False).to_dict() # counts only, no feature relationship

csv=OUT/"dp4_candidate_matrix_v1.csv"
x.to_csv(csv,index=False)
fingerprint=hashlib.sha256(csv.read_bytes()).hexdigest()

protocol={
 "version":"PMPD_V5_9K_DP4_CANDIDATE_MATRIX_V1",
 "anchor":"DP4_FULL_STACK_FIRST_CLEAR",
 "rows":len(x),"unique_decisions":int(x["decision_id"].nunique()),
 "candidate_groups":groups,
 "prohibited_post_anchor_fields":prohibited,
 "prohibited_hits":hits,
 "missingness":missing,
 "partition_counts":part_counts,
 "direction_counts":dir_counts,
 "outcome_counts_only":out_counts,
 "matrix_sha256":fingerprint,
 "governance":{
   "inherited_v4_weights":False,
   "outcome_relationships_characterized":False,
   "thresholds_fit":False,
   "model_fit":False,
   "production_rule_authorized":False,
   "post_dp4_features_allowed":False,
   "validation_threshold_reestimation_allowed":False
 }
}
(OUT/"dp4_candidate_matrix_protocol_v1.json").write_text(json.dumps(protocol,indent=2,default=str),encoding="utf-8")

print("PARTITION_COUNTS =",part_counts)
print("DIRECTION_COUNTS =",dir_counts)
print("OUTCOME_COUNTS_ONLY =",out_counts)
print("CANDIDATE_GROUPS =",json.dumps(groups,indent=2))
print("PROHIBITED_POST_ANCHOR_HITS =",hits)
print("MATRIX_SHA256 =",fingerprint)
print("OUTCOME_RELATIONSHIPS_CHARACTERIZED=False")
print("THRESHOLDS_FIT=False")
print("MODEL_FIT=False")
print("PRODUCTION_RULE_AUTHORIZED=False")
print("DP4_CANDIDATE_MATRIX_GATE=PASS")
