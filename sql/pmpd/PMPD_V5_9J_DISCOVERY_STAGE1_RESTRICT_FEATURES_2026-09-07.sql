-- PM+PD V5 9J Discovery Stage 1 restricted feature-set follow-up
update project_state
set metadata_json=coalesce(metadata_json,'{}'::jsonb)||jsonb_build_object(
 'pmpd_v5_9j_discovery_stage1_initial_gate','PASS',
 'pmpd_v5_9j_discovery_stage1_initial_rows',145692,
 'pmpd_v5_9j_discovery_stage1_initial_validation_outcomes_characterized',false,
 'pmpd_v5_9j_discovery_stage1_followup','RESTRICT_FEATURE_SET_BEFORE_INTERPRETATION'
),
last_decision='9J Discovery Stage 1 anti-peek gate passed. Before interpretation, exclude raw RTH VWAP absolute price, version metadata, and the invalid legacy first-DP345 structural-clearance flag; rerun Discovery only. Validation and 9K remain unopened.',
updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
