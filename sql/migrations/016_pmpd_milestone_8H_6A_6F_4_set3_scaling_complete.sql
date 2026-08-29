-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Milestone Update — 8H-6A-6F-4 SET_3 Controlled Scaling COMPLETE
-- Generated: 2026-08-28
--
-- Recommended repo location:
--   sql/migrations/016_pmpd_milestone_8H_6A_6F_4_set3_scaling_complete.sql
--
-- VERIFIED EVIDENCE
--   SET_3 / 2025 initial dry-run:
--     28 total / 0 complete / 28 needing download.
--   Controlled execution:
--     28 downloaded / 0 skipped complete / 0 failed.
--   Post-acquisition dry-run:
--     28 complete / 0 needing download.
--   Final --execute resume test:
--     28 complete / 0 needing download.
--     No redundant download and no API-key prompt.
--
-- CUMULATIVE 2025 COVERAGE
--   SET_1: 28/28
--   SET_2: 28/28
--   SET_3: 28/28
--   Total: 84/112 (75%)
--
-- SAFETY
--   * Keeps parent phase 8H-6 ACTIVE.
--   * Keeps 8H-7 as next top-level phase.
--   * Does not declare the full frozen universe complete.
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
    '8H-6A-6F-4 SET_3 Controlled Scaling completed',
    'SET_3 x 2025 completed successfully through the frozen-universe acquisition workflow and passed post-acquisition completeness and no-op resume validation.',
    'This extends the proven acquisition workflow to three independent authoritative sets, covering 84 of 112 PMPD universe symbols for 2025 before the final SET_4 scaling stage.',
    'SET_3/2025: initial dry-run 28 total / 0 complete / 28 needing download; execution 28 downloaded / 0 skipped / 0 failed; post-acquisition 28 complete / 0 remaining; final --execute resume produced no redundant download and no credential prompt.',
    'V4',
    jsonb_build_object(
        'milestone_code', '8H-6A-6F-4',
        'milestone_name', 'SET_3 Controlled Scaling',
        'milestone_status', 'COMPLETE',
        'universe_code', 'PMPD_112_V1',
        'controlled_set', 'SET_3',
        'controlled_year', 2025,
        'partition_count', 28,
        'execution_downloaded', 28,
        'execution_failed', 0,
        'post_acquisition_complete', 28,
        'post_acquisition_needing_download', 0,
        'resume_validation', 'PASS',
        'cumulative_2025_symbols_complete', 84,
        'cumulative_2025_universe_symbols', 112,
        'cumulative_2025_percent', 75,
        'validation', 'PASS',
        'completed_at', now()
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = '8H-6A-6F-4 SET_3 Controlled Scaling completed'
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
    last_decision = '8H-6A-6F-4 passed: SET_3 x 2025 is complete and resumable. SET_1 through SET_3 provide 84/112 complete 2025 symbols; proceed to 8H-6A-6F-5 SET_4 scaling.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            '8H-6A-6F-4_status', 'COMPLETE',
            '8H-6A-6F-4_validation', 'PASS',
            'historical_engine_status', 'THREE_SET_SCALING_PROVEN',
            'controlled_acquisition_sets_complete', 3,
            'controlled_2025_symbols_complete', 84,
            'controlled_2025_symbols_total', 112,
            'controlled_2025_percent_complete', 75,
            'controlled_acquisition_resume', 'PASS',
            '8H-6A_next', '8H-6A-6F-5'
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
  and pd.title = '8H-6A-6F-4 SET_3 Controlled Scaling completed';

select
    s.strategy_code,
    ps.active_phase_code,
    ps.next_phase_code,
    ps.metadata_json ->> '8H-6A-6F-4_status' as milestone_status,
    ps.metadata_json ->> 'historical_engine_status' as historical_engine_status,
    ps.metadata_json ->> 'controlled_2025_symbols_complete' as symbols_complete_2025,
    ps.metadata_json ->> 'controlled_2025_percent_complete' as percent_complete_2025,
    ps.metadata_json ->> 'controlled_acquisition_resume' as resume_validation,
    ps.metadata_json ->> '8H-6A_next' as next_implementation_step,
    ps.last_decision
from public.project_state ps
join public.strategies s on s.strategy_id = ps.strategy_id
where s.strategy_code = 'PMPD';
