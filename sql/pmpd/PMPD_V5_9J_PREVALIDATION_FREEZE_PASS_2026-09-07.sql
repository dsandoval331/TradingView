-- PM+PD V5 9J pre-validation freeze PASS
update project_state
set metadata_json=coalesce(metadata_json,'{}'::jsonb)||jsonb_build_object(
 'pmpd_v5_9j_prevalidation_freeze_gate','PASS',
 'pmpd_v5_9j_validation_freeze_fingerprint','7e754fd754c46cd3d5b6e3de34bd0b2074cee9d50c4b5b1577cd0b91d2a3eadf',
 'pmpd_v5_9j_frozen_continuous_rows',18,
 'pmpd_v5_9j_frozen_binary_hypotheses',3,
 'pmpd_v5_9j_validation_outcomes_characterized_before_freeze',false,
 'pmpd_v5_9j_cutpoint_reestimation_in_validation_allowed',false,
 'pmpd_v5_9j_validation_status','AUTHORIZED_UNDER_FROZEN_PROTOCOL'
),
last_decision='9J pre-validation freeze passed. Validation A/B authorized under fingerprinted frozen protocol only. Cutpoints cannot be re-estimated. 9K unopened.',
updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
