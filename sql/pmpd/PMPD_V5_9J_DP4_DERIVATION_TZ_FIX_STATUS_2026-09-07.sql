-- PM+PD V5 9J DP4 derivation timezone-script fix status backup
update project_state
set metadata_json = coalesce(metadata_json,'{}'::jsonb) || jsonb_build_object(
  'pmpd_v5_9j_vwap_event_path_v2_status','DP4_DERIVATION_SCRIPT_TZ_DTYPE_FIX_REQUIRED',
  'pmpd_v5_9j_vwap_event_path_v2_dp4_derivation_error',
  'Timezone-aware UTC loss timestamps could not be assigned into timezone-naive derived column; script-only dtype initialization bug, no data or methodology failure.'
),
last_decision = '9J DP4 semantic derivation encountered a pandas timezone dtype assignment error while reconstructing event_last_vwap_loss_timestamp_utc. Certified V2 data and DP4 methodology remain valid. Patch derivation script to initialize derived timestamp column as UTC-aware, then rerun derivation certification. 9J remains active; 9K unopened.',
updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
