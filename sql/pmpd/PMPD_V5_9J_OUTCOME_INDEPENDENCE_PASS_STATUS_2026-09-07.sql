-- PM+PD V5 9J outcome-independence PASS / frozen-outcome join pending
update project_state
set metadata_json = coalesce(metadata_json,'{}'::jsonb) || jsonb_build_object(
  'pmpd_v5_9j_vwap_event_path_v2_status','OUTCOME_INDEPENDENCE_CERTIFIED_FROZEN_OUTCOME_JOIN_PENDING',
  'pmpd_v5_9j_vwap_event_path_v2_outcome_independence_certification','PASS',
  'pmpd_v5_9j_vwap_event_path_v2_feature_construction_status','CERTIFIED_OUTCOME_INDEPENDENT',
  'pmpd_v5_9j_vwap_event_path_v2_next_gate','JOIN_FROZEN_9H_OUTCOMES_BY_DECISION_ID_AND_AUDIT_JOIN'
),
last_decision='9J VWAP Event-Path V2/DP4 feature construction certified outcome-independent with zero failed checks. Frozen 9H outcomes may now be joined by decision_id only. Next: audited frozen-outcome join, then Discovery-only characterization. Validation A/B and 9K remain unopened.',
updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
