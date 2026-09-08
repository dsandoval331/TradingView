-- PM+PD V5 9J DP4 derivation duplicate decision_id script-fix status backup
update project_state
set metadata_json = coalesce(metadata_json,'{}'::jsonb) || jsonb_build_object(
  'pmpd_v5_9j_vwap_event_path_v2_status','DP4_DERIVATION_SCRIPT_DUPLICATE_DECISION_ID_FIX_REQUIRED',
  'pmpd_v5_9j_vwap_event_path_v2_dp4_derivation_error',
  'Integrity comparison constructed duplicate decision_id column in temporary comparison frame; script-only bug, no data or methodology failure.'
),
last_decision = '9J DP4 semantic derivation passed timezone reconstruction but encountered a script-only duplicate decision_id column in the source-field preservation comparison. Certified V2 data and DP4 methodology remain valid. Patch comparison column construction and rerun derivation certification. 9J remains active; 9K unopened.',
updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
