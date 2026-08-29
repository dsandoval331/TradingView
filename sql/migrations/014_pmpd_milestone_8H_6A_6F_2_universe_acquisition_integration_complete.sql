-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Milestone Update — 8H-6A-6F-2 Universe-to-Acquisition Integration COMPLETE
-- Generated: 2026-08-28
--
-- Recommended repo location:
--   sql/migrations/014_pmpd_milestone_8H_6A_6F_2_universe_acquisition_integration_complete.sql
--
-- VERIFIED EVIDENCE
--   * SET_1 / 2025 dry-run before acquisition:
--       28 total, 3 complete, 25 needing download.
--   * Controlled execution:
--       28 total, 25 downloaded, 3 skipped complete, 0 failed.
--   * Post-acquisition dry-run:
--       28 total, 28 complete, 0 needing download.
--   * Post-acquisition --execute resume check:
--       28 total, 28 complete, 0 needing download.
--       Exited with "Nothing to download."
--       No API-key prompt / no download required.
--
-- SAFETY
--   * Keeps parent phase 8H-6 ACTIVE.
--   * Keeps 8H-7 as next top-level phase.
--   * Records controlled scaling proof without declaring the full historical
--     universe/dataset complete.
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
    '8H-6A-6F-2 Universe-to-Acquisition Integration completed',
    'The frozen PMPD_112_V1 universe loader is successfully integrated with the hardened acquisition engine. SET_1 x 2025 was acquired and then proven fully resumable/idempotent.',
    'A controlled 28-partition scale test verifies that authoritative universe selection, manifest/cache completeness detection, acquisition execution, and no-op resume behavior work together before broader historical-universe bootstrap.',
    'Initial dry-run: 28 total / 3 complete / 25 need download. Execution: 25 downloaded / 3 skipped complete / 0 failed. Post-acquisition dry-run: 28 complete / 0 need download. Final --execute resume check: all 28 complete; nothing downloaded and no credential prompt required.',
    'V4',
    jsonb_build_object(
        'milestone_code', '8H-6A-6F-2',
        'milestone_name', 'Universe-to-Acquisition Integration',
        'milestone_status', 'COMPLETE',
        'universe_code', 'PMPD_112_V1',
        'controlled_set', 'SET_1',
        'controlled_year', 2025,
        'partition_count', 28,
        'initial_complete', 3,
        'initial_needing_download', 25,
        'execution_downloaded', 25,
        'execution_skipped_complete', 3,
        'execution_failed', 0,
        'post_acquisition_complete', 28,
        'post_acquisition_needing_download', 0,
        'resume_execute_behavior', 'NO_OP_COMPLETE',
        'resume_api_key_prompt_required', false,
        'validation', 'PASS',
        'completed_at', now()
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = '8H-6A-6F-2 Universe-to-Acquisition Integration completed'
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
    last_decision = '8H-6A-6F-2 Universe-to-Acquisition Integration passed: SET_1 x 2025 is complete and resumable with 28/28 partitions; proceed to the next controlled acquisition-scaling milestone.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            '8H-6A-6F-2_status', 'COMPLETE',
            '8H-6A-6F-2_validation', 'PASS',
            'historical_engine_status', 'CONTROLLED_SET_ACQUISITION_PROVEN',
            'controlled_acquisition_set', 'SET_1',
            'controlled_acquisition_year', 2025,
            'controlled_acquisition_partitions_complete', 28,
            'controlled_acquisition_partitions_remaining', 0,
            'controlled_acquisition_resume', 'PASS',
            '8H-6A_next', '8H-6A-6F-3'
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
join public.strategies s
    on s.strategy_id = pd.strategy_id
where s.strategy_code = 'PMPD'
  and pd.title = '8H-6A-6F-2 Universe-to-Acquisition Integration completed';

select
    s.strategy_code,
    ps.active_phase_code,
    ps.next_phase_code,
    ps.metadata_json ->> '8H-6A-6F-2_status' as milestone_status,
    ps.metadata_json ->> 'historical_engine_status' as historical_engine_status,
    ps.metadata_json ->> 'controlled_acquisition_partitions_complete' as partitions_complete,
    ps.metadata_json ->> 'controlled_acquisition_resume' as resume_validation,
    ps.metadata_json ->> '8H-6A_next' as next_implementation_step,
    ps.last_decision
from public.project_state ps
join public.strategies s
    on s.strategy_id = ps.strategy_id
where s.strategy_code = 'PMPD';
