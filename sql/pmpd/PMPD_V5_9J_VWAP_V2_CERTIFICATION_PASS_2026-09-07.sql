-- PM+PD V5 9J VWAP Event-Path V2 certification PASS status backup
update project_state
set metadata_json = coalesce(metadata_json,'{}'::jsonb) || jsonb_build_object(
  'pmpd_v5_9j_vwap_event_path_v2_status','CERTIFIED_FEATURE_DATASET_STRUCTURAL_CLEARANCE_TAXONOMY_PENDING',
  'pmpd_v5_9j_vwap_event_path_v2_certification','PASS',
  'pmpd_v5_9j_vwap_event_path_v2_failed_checks',jsonb_build_array(),
  'pmpd_v5_9j_vwap_event_path_v2_rows',450491,
  'pmpd_v5_9j_vwap_event_path_v2_unique_decisions',450491,
  'pmpd_v5_9j_vwap_event_path_v2_events',44627,
  'pmpd_v5_9j_vwap_event_path_v2_symbols',112,
  'pmpd_v5_9j_vwap_event_path_v2_primary_rows',266076,
  'pmpd_v5_9j_vwap_event_path_v2_columns',50,
  'pmpd_v5_9j_vwap_event_path_v2_fingerprint','1f3e0d2bec2c6257bb6b372d324e9b0bc6948d6f02c5713b5ae10091573f0b56',
  'pmpd_v5_9j_vwap_event_path_v2_discovery_rows',145692,
  'pmpd_v5_9j_vwap_event_path_v2_validation_a_rows',147486,
  'pmpd_v5_9j_vwap_event_path_v2_validation_b_rows',157313,
  'pmpd_v5_9j_vwap_event_path_v2_v1_v2_max_abs_vwap_diff',0.0,
  'pmpd_v5_9j_vwap_event_path_v2_structural_clearance_field_status','WITHHELD_PENDING_DP4_TAXONOMY_VERIFICATION'
),
last_decision = '9J VWAP Event-Path V2 full50 dataset CERTIFIED: all population, identity, temporal/leakage, partition, value-sanity, and V1/V2 VWAP parity checks passed with zero failures. Certified fingerprint 1f3e0d2bec2c6257bb6b372d324e9b0bc6948d6f02c5713b5ae10091573f0b56. The event_vwap_loss_after_structural_clearance feature remains withheld until DP3/DP4/DP5 taxonomy is verified; Discovery and 9K remain blocked until that 9J gate is resolved.',
updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
