-- PMPD V5 thread-handoff checkpoint (backup)
begin;
with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.project_state ps
set active_phase_code='9J',
    active_phase_name='Alternative Entry / Confirmation Architectures',
    next_phase_code='9K',
    next_phase_name='Evidence-Derived Classification / Scoring',
    last_decision='Thread handoff checkpoint: 9J structural architecture batch complete; VWAP V1 enrichment certified and snapshot analysis completed without promotion. V1 session-cumulative path fields are not event-specific. Next work is 9J VWAP Event-Path V2 anchored at DP1 contact, followed by validation/robustness and 9J closeout. Supabase is upgraded and database size is not a current research constraint.',
    metadata_json=coalesce(ps.metadata_json,'{}'::jsonb)||jsonb_build_object(
      'v5_current_phase','9J','v5_current_substep','9J-VWAP-EVENT-PATH-V2',
      'v5_9j_status','ACTIVE','v5_9j_structural_batch_status','COMPLETE',
      'v5_9j_vwap_v1_integrity','PASS','v5_9j_vwap_snapshot_status','COMPLETE_NO_PROMOTION',
      'v5_9j_vwap_event_path_v2_required',true,'v5_production_rule_authorized',false,
      'supabase_capacity_status','UPGRADED_NO_CURRENT_DB_LIMITATION',
      'supabase_capacity_is_research_constraint',false,'thread_handoff_checkpoint_date','2026-09-07'),
    updated_at=now()
from pmpd where ps.strategy_id=pmpd.strategy_id;
commit;
