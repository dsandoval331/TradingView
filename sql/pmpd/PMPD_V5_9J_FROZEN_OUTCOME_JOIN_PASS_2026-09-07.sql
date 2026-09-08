-- PM+PD V5 9J audited frozen-outcome join PASS
update project_state
set metadata_json=coalesce(metadata_json,'{}'::jsonb)||jsonb_build_object(
 'pmpd_v5_9j_vwap_event_path_v2_status','FROZEN_OUTCOME_JOIN_CERTIFIED_DISCOVERY_PENDING',
 'pmpd_v5_9j_frozen_outcome_join_gate','PASS',
 'pmpd_v5_9j_frozen_outcome_join_fingerprint','e9dbb42aedd9293c7dde24574605f1fdf7049d3cad23fd3fd071e7d4aa2c0910',
 'pmpd_v5_9j_join_rows',450491,
 'pmpd_v5_9j_join_discovery_rows',145692,
 'pmpd_v5_9j_join_validation_a_rows',147486,
 'pmpd_v5_9j_join_validation_b_rows',157313,
 'pmpd_v5_9j_join_validation_outcomes_characterized',false
),
last_decision='9J audited frozen 9H outcome join PASSED. Canonical outcome preserves all four frozen states. Proceed to Discovery-only characterization; Validation A/B and 9K remain unopened.',
updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
