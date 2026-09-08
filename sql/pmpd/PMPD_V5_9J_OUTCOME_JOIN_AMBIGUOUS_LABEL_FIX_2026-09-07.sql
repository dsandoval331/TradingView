-- PM+PD V5 9J canonical outcome label mapping fix
update project_state
set metadata_json=coalesce(metadata_json,'{}'::jsonb)||jsonb_build_object(
 'pmpd_v5_9j_vwap_event_path_v2_status','FROZEN_OUTCOME_JOIN_LABEL_MAPPING_FIX_REQUIRED',
 'pmpd_v5_9j_outcome_unmapped_label','AMBIGUOUS_SAME_BAR',
 'pmpd_v5_9j_outcome_unmapped_count',1178
),
last_decision='9J canonical outcome join safely stopped because AMBIGUOUS_SAME_BAR was not mapped by the generic categorical resolver. Preserve the canonical frozen label explicitly; patch label mapping only. Validation and 9K remain unopened.',
updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
