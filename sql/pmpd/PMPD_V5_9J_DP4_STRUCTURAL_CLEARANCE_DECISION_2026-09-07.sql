-- PM+PD V5 9J DP4 structural-clearance taxonomy decision backup
update project_state
set metadata_json = coalesce(metadata_json,'{}'::jsonb) || jsonb_build_object(
  'pmpd_v5_9j_vwap_event_path_v2_status','CERTIFIED_CORE_DP4_STRUCTURAL_CLEARANCE_SEMANTIC_FIX_REQUIRED',
  'pmpd_v5_9j_vwap_event_path_v2_structural_clearance_semantics','DP4_FULL_STACK_FIRST_CLEAR',
  'pmpd_v5_9j_vwap_event_path_v2_current_structural_clearance_field_status','INVALID_FOR_ANALYSIS_FIRST_DP345_ANCHOR',
  'pmpd_v5_9j_vwap_event_path_v2_events_with_dp4',22736,
  'pmpd_v5_9j_vwap_event_path_v2_events_first_any_differs_from_dp4',15138,
  'pmpd_v5_9j_vwap_event_path_v2_events_no_dp4_in_comparison',14814,
  'pmpd_v5_9j_vwap_event_path_v2_dp4_fix_strategy','DERIVE_CORRECTED_DP4-ANCHORED_FIELD_FROM_CERTIFIED_V2_AND_PARENT_TIMESTAMPS_WITHOUT_RECOMPUTING_MARKET_PATH'
),
last_decision = '9J taxonomy gate resolved: structural clearance is DP4_FULL_STACK_FIRST_CLEAR specifically. Existing event_vwap_loss_after_structural_clearance is analytically invalid because implementation anchors to first DP3/DP4/DP5, which is DP3 when present. 15,138 events with DP4 have an earlier DP3; 14,814 compared events have no DP4. Preserve certified 50-column core, derive corrected DP4-anchored loss-after-clearance field in a new artifact, certify derivation, then proceed to Discovery. 9K remains unopened.',
updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
