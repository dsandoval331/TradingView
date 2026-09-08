-- PM+PD V5 9J Discovery evidence PASS / pre-validation freeze pending
update project_state
set metadata_json=coalesce(metadata_json,'{}'::jsonb)||jsonb_build_object(
 'pmpd_v5_9j_discovery_evidence_gate','PASS',
 'pmpd_v5_9j_discovery_candidate_freeze_rows',18,
 'pmpd_v5_9j_validation_outcomes_characterized',false,
 'pmpd_v5_9j_next_action','FREEZE_VALIDATION_PROTOCOL'
),
last_decision='9J Discovery evidence summary passed. Freeze exact unconditional Discovery quartiles for six compact VWAP-path features plus pre-specified semantic binary hypotheses before opening Validation A/B. No threshold optimization; 9K unopened.',
updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
