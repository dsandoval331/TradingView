-- PM+PD V5 9J VWAP Event-Path V2 stale-artifact reconciliation
-- Backup of project_state update performed 2026-09-07.
update project_state
set metadata_json = coalesce(metadata_json,'{}'::jsonb) || jsonb_build_object(
  'pmpd_v5_9j_vwap_event_path_v2_status','STALE_23_COLUMN_ARTIFACT_IDENTIFIED_CURRENT_CORE_50_COLUMN_RERUN_REQUIRED',
  'pmpd_v5_9j_vwap_event_path_v2_live_msft_rows',4142,
  'pmpd_v5_9j_vwap_event_path_v2_live_msft_columns',50,
  'pmpd_v5_9j_vwap_event_path_v2_stale_artifact_columns',23,
  'pmpd_v5_9j_vwap_event_path_v2_rerun_reason',
  'Existing 112-symbol CSV/ZIP were produced under an earlier schema. Current patched core build_symbol returns 50 columns and roundtrip export preserves all 50. Preserve stale artifact for provenance and rerun full universe under current core before certification.'
),
last_decision = '9J VWAP Event-Path V2 runtime-vs-artifact diagnostic resolved the schema contradiction: current patched core produces 50-column V2 rows and pandas roundtrip preserves them, while the existing 17:11 full-universe CSV/ZIP retain the stale 23-column schema. Preserve stale artifact; rerun 112-symbol universe under current core into a new output directory, then certify. 9J remains active; 9K remains unopened.',
updated_at = now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
