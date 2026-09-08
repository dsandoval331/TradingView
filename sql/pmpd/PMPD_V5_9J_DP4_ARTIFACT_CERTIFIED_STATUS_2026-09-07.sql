-- PM+PD V5 9J certified DP4 artifact status backup
update project_state
set metadata_json = coalesce(metadata_json,'{}'::jsonb) || jsonb_build_object(
  'pmpd_v5_9j_vwap_event_path_v2_status','DP4_DERIVED_ARTIFACT_CERTIFIED_OUTCOME_INDEPENDENCE_GATE_PENDING',
  'pmpd_v5_9j_vwap_event_path_v2_dp4fix_fingerprint','9db7404bbf69d9b31b5ad93edfce943bdc515b70146e0d07f0fdda331f9a3a57',
  'pmpd_v5_9j_vwap_event_path_v2_dp4fix_rows',450491,
  'pmpd_v5_9j_vwap_event_path_v2_dp4fix_columns',55,
  'pmpd_v5_9j_vwap_event_path_v2_dp4fix_corrected_true_rows',108640,
  'pmpd_v5_9j_vwap_event_path_v2_dp4fix_corrected_true_events',14530,
  'pmpd_v5_9j_vwap_event_path_v2_structural_clearance_semantics','DP4_FULL_STACK_FIRST_CLEAR'
),
last_decision='9J DP4 semantic correction certified; next gate is explicit outcome-independence certification before frozen-outcome join. 9K remains unopened.',
updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
