-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Milestone Update — 8H-6A-6F-3 Cross-Set Controlled Scaling COMPLETE
-- Generated: 2026-08-28
--
-- Recommended repo location:
--   sql/migrations/015_pmpd_milestone_8H_6A_6F_3_cross_set_scaling_complete.sql
--
-- VERIFIED EVIDENCE
--   SET_2 / 2025 initial dry-run:
--     28 total / 0 complete / 28 needing download.
--   Controlled execution:
--     28 downloaded / 0 skipped complete / 0 failed.
--   Post-acquisition dry-run:
--     28 complete / 0 needing download.
--   Final --execute resume test:
--     28 complete / 0 needing download.
--     "All requested partitions are already complete. Nothing to download."
--     No API-key prompt and no download required.
--
-- CUMULATIVE CONTROLLED COVERAGE
--   SET_1 / 2025: 28/28 complete
--   SET_2 / 2025: 28/28 complete
--   Total:          56/112 PMPD symbols for 2025
--
-- SAFETY
--   * Keeps parent phase 8H-6 ACTIVE.
--   * Keeps 8H-7 as next top-level phase.
--   * Does not declare the full 112-symbol historical dataset complete.
-- ============================================================================

begin;

with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
insert into public.project_decisions (
    strategy_id,
    title,
    decision,
    rationale,
    evidence,
    affects_model_version,
    metadata_json
)
select
    pmpd.strategy_id,
    '8H-6A-6F-3 Cross-Set Controlled Scaling completed',
    'The hardened frozen-universe acquisition workflow generalized successfully to a second independent 28-symbol set without Python code changes. SET_2 x 2025 is complete and resumable.',
    'Successful acquisition and no-op resume behavior on SET_2 demonstrates cross-set scalability beyond the original SET_1 proof before broader universe bootstrap.',
    'SET_2/2025 initial dry-run: 28 total, 0 complete, 28 need download. Execution: 28 downloaded, 0 skipped, 0 failed. Post-acquisition dry-run: 28 complete, 0 need download. Final --execute resume: nothing to download and no credential prompt required. Cumulative SET_1 + SET_2 coverage: 56/112 symbols for 2025.',
    'V4',
    jsonb_build_object(
        'milestone_code', '8H-6A-6F-3',
        'milestone_name', 'Cross-Set Controlled Scaling',
        'milestone_status', 'COMPLETE',
        'universe_code', 'PMPD_112_V1',
        'controlled_set', 'SET_2',
        'controlled_year', 2025,
        'partition_count', 28,
        'initial_complete', 0,
        'initial_needing_download', 28,
        'execution_downloaded', 28,
        'execution_skipped_complete', 0,
        'execution_failed', 0,
        'post_acquisition_complete', 28,
        'post_acquisition_needing_download', 0,
        'resume_execute_behavior', 'NO_OP_COMPLETE',
        'resume_api_key_prompt_required', false,
        'cumulative_2025_symbols_complete', 56,
        'cumulative_2025_universe_symbols', 112,
        'validation', 'PASS',
        'completed_at', now()
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = '8H-6A-6F-3 Cross-Set Controlled Scaling completed'
      and d.status = 'active'
);

with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
update public.project_state ps
set
    active_phase_code = '8H-6',
    active_phase_name = 'Historical Engine & Ingestion',
    next_phase_code = '8H-7',
    next_phase_name = 'Small-Sample Parity Validation',
    last_decision = '8H-6A-6F-3 Cross-Set Controlled Scaling passed: SET_2 x 2025 is complete and resumable; SET_1 + SET_2 provide 56/112 complete 2025 partitions. Proceed to 8H-6A-6F-4.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            '8H-6A-6F-3_status', 'COMPLETE',
            '8H-6A-6F-3_validation', 'PASS',
            'historical_engine_status', 'CROSS_SET_SCALING_PROVEN',
            'controlled_acquisition_sets_complete', 2,
            'controlled_2025_symbols_complete', 56,
            'controlled_2025_symbols_total', 112,
            'controlled_acquisition_resume', 'PASS',
            '8H-6A_next', '8H-6A-6F-4'
        ),
    updated_at = now()
from pmpd
where ps.strategy_id = pmpd.strategy_id;

commit;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

select
    pd.title,
    pd.status,
    pd.decision_date
from public.project_decisions pd
join public.strategies s on s.strategy_id = pd.strategy_id
where s.strategy_code = 'PMPD'
  and pd.title = '8H-6A-6F-3 Cross-Set Controlled Scaling completed';

select
    s.strategy_code,
    ps.active_phase_code,
    ps.next_phase_code,
    ps.metadata_json ->> '8H-6A-6F-3_status' as milestone_status,
    ps.metadata_json ->> 'historical_engine_status' as historical_engine_status,
    ps.metadata_json ->> 'controlled_2025_symbols_complete' as symbols_complete_2025,
    ps.metadata_json ->> 'controlled_acquisition_resume' as resume_validation,
    ps.metadata_json ->> '8H-6A_next' as next_implementation_step,
    ps.last_decision
from public.project_state ps
join public.strategies s on s.strategy_id = ps.strategy_id
where s.strategy_code = 'PMPD';
