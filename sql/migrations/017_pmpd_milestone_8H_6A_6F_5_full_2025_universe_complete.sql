-- ============================================================================
-- PMPD — 8H-6A-6F-5 Full 2025 Universe Acquisition COMPLETE
-- Migration 017
-- Generated: 2026-08-28
-- ============================================================================

begin;

with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
insert into public.project_decisions (
    strategy_id, title, decision, rationale, evidence,
    affects_model_version, metadata_json
)
select
    pmpd.strategy_id,
    '8H-6A-6F-5 Full PMPD_112_V1 2025 acquisition completed',
    'SET_4 x 2025 completed successfully, bringing PMPD_112_V1 to 112/112 complete 2025 symbol/year partitions.',
    'All four authoritative 28-symbol sets passed acquisition, post-acquisition completeness, and no-op resume validation. Dataset-level integrity/readiness review is required before treating 2025 as research-ready.',
    'SET_4 execution: 28 downloaded / 0 skipped / 0 failed. Post-check: 28/28 complete. Final --execute resume: nothing to download. Cumulative PMPD_112_V1 2025 coverage: 112/112 symbols (100%).',
    'V4',
    jsonb_build_object(
        'milestone_code', '8H-6A-6F-5',
        'milestone_name', 'Full PMPD_112_V1 2025 Acquisition',
        'milestone_status', 'COMPLETE',
        'universe_code', 'PMPD_112_V1',
        'year', 2025,
        'sets_complete', 4,
        'symbols_complete', 112,
        'symbols_total', 112,
        'percent_complete', 100,
        'resume_validation', 'PASS',
        'research_ready', false,
        'completed_at', now()
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = '8H-6A-6F-5 Full PMPD_112_V1 2025 acquisition completed'
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
    historical_dataset_status = 'PMPD_112_V1_2025_ACQUIRED_INTEGRITY_REVIEW_PENDING',
    last_decision = '8H-6A-6F-5 passed: PMPD_112_V1 is 112/112 complete for 2025 with resume validation. Proceed to 8H-6A-6G dataset-level integrity and readiness review before 8H-7.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            '8H-6A-6F-5_status', 'COMPLETE',
            '8H-6A-6F-5_validation', 'PASS',
            'historical_engine_status', 'FULL_2025_UNIVERSE_ACQUIRED',
            'pmpd_112_2025_symbols_complete', 112,
            'pmpd_112_2025_symbols_total', 112,
            'pmpd_112_2025_percent_complete', 100,
            'pmpd_112_2025_resume_validation', 'PASS',
            'pmpd_112_2025_research_ready', false,
            '8H-6A_next', '8H-6A-6G'
        ),
    updated_at = now()
from pmpd
where ps.strategy_id = pmpd.strategy_id;

commit;

-- Verification
select
    s.strategy_code,
    ps.active_phase_code,
    ps.next_phase_code,
    ps.historical_dataset_status,
    ps.metadata_json ->> '8H-6A-6F-5_status' as milestone_status,
    ps.metadata_json ->> 'historical_engine_status' as historical_engine_status,
    ps.metadata_json ->> 'pmpd_112_2025_symbols_complete' as symbols_complete_2025,
    ps.metadata_json ->> 'pmpd_112_2025_percent_complete' as percent_complete_2025,
    ps.metadata_json ->> 'pmpd_112_2025_resume_validation' as resume_validation,
    ps.metadata_json ->> 'pmpd_112_2025_research_ready' as research_ready,
    ps.metadata_json ->> '8H-6A_next' as next_implementation_step,
    ps.last_decision
from public.project_state ps
join public.strategies s on s.strategy_id = ps.strategy_id
where s.strategy_code = 'PMPD';
