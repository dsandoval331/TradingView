-- PM+PD V5 9J VWAP Event-Path V2 corrected build status backup
update project_state
set metadata_json = coalesce(metadata_json,'{}'::jsonb) || jsonb_build_object(
  'pmpd_v5_9j_vwap_event_path_v2_status','FULL50_BUILD_COMPLETE_CERTIFICATION_PENDING',
  'pmpd_v5_9j_vwap_event_path_v2_rows',450491,
  'pmpd_v5_9j_vwap_event_path_v2_unique_decisions',450491,
  'pmpd_v5_9j_vwap_event_path_v2_events',44627,
  'pmpd_v5_9j_vwap_event_path_v2_symbols',112,
  'pmpd_v5_9j_vwap_event_path_v2_primary_rows',266076,
  'pmpd_v5_9j_vwap_event_path_v2_columns',50,
  'pmpd_v5_9j_vwap_event_path_v2_fingerprint','1f3e0d2bec2c6257bb6b372d324e9b0bc6948d6f02c5713b5ae10091573f0b56',
  'pmpd_v5_9j_vwap_event_path_v2_output_dir','pmpd_v5_9j_vwap_event_path_v2_full50'
),
last_decision = '9J VWAP Event-Path V2 corrected full-universe rerun completed under current patched core. Schema/population gate passed: 450,491 rows, 450,491 unique decisions, 44,627 events, 112 symbols, 266,076 primary rows, 50 columns, no missing required columns. Fingerprint 1f3e0d2bec2c6257bb6b372d324e9b0bc6948d6f02c5713b5ae10091573f0b56. Certification is next; Discovery and 9K remain blocked until certification passes.',
updated_at = now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
