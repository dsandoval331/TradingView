-- PM+PD V5 9J frozen validation PASS; robustness adjudication pending
update project_state
set metadata_json=coalesce(metadata_json,'{}'::jsonb)||jsonb_build_object(
 'pmpd_v5_9j_frozen_validation_gate','PASS',
 'pmpd_v5_9j_validation_a_rows',147486,
 'pmpd_v5_9j_validation_b_rows',157313,
 'pmpd_v5_9j_cutpoints_reestimated',false,
 'pmpd_v5_9j_production_rule_authorized',false,
 'pmpd_v5_9j_next_action','VALIDATION_ROBUSTNESS_AND_FINAL_9J_ADJUDICATION'
),
last_decision='9J frozen Validation A/B passed under frozen protocol. Continuous spread alone is not sufficient for final adjudication; compare Discovery vs Validation shape/orientation and frozen-cutpoint symbol-cluster robustness before 9J closeout. 9K unopened.',
updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
