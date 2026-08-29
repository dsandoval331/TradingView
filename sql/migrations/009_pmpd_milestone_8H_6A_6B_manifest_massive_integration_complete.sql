-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Milestone Update — 8H-6A-6B Manifest + Massive Downloader Integration COMPLETE
-- Generated: 2026-08-28
--
-- Recommended repo location:
--   sql/migrations/009_pmpd_milestone_8H_6A_6B_manifest_massive_integration_complete.sql
--
-- PURPOSE
--   Record completion of implementation milestone 8H-6A-6B while keeping
--   top-level phase 8H-6 Historical Engine & Ingestion ACTIVE.
--
-- VERIFIED EVIDENCE
--   Integration test passed:
--     - First pass action = DOWNLOADED
--     - Rows = 860
--     - Manifest download status = DOWNLOADED
--     - Manifest validation status = PASS
--     - SHA256 length = 64
--     - Second pass action = SKIPPED_COMPLETE
--     - Resume/skip behavior = PASS
--
-- SAFETY
--   * Does not complete 8H-6.
--   * Does not change next phase 8H-7.
--   * Does not alter Second1M tables.
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
    '8H-6A-6B Manifest + Massive Downloader Integration completed',
    'The Massive downloader and MARKET_CACHE_V1 local manifest are successfully integrated. Completed ranges are persisted, validated, hashed, and skipped on repeat acquisition.',
    'This integration proves the acquisition path can safely avoid redundant downloads and resume around previously completed work before production symbol/year acquisition begins.',
    'Integration test passed on 2026-08-28: first action=DOWNLOADED; rows=860; manifest download_status=DOWNLOADED; validation_status=PASS; SHA256 length=64; second action=SKIPPED_COMPLETE; resume/skip behavior=PASS.',
    'V4',
    jsonb_build_object(
        'milestone_code', '8H-6A-6B',
        'milestone_name', 'Manifest + Massive Downloader Integration',
        'milestone_status', 'COMPLETE',
        'component', 'MARKET_CACHE_V1',
        'integration_test_status', 'PASS',
        'first_action', 'DOWNLOADED',
        'row_count', 860,
        'second_action', 'SKIPPED_COMPLETE',
        'resume_skip_behavior', 'PASS',
        'sha256_length', 64,
        'completed_at', now()
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = '8H-6A-6B Manifest + Massive Downloader Integration completed'
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
    last_decision = '8H-6A-6B Manifest + Massive Downloader Integration passed; proceed to 8H-6A-6C Production Symbol/Year Acquisition.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            '8H-6A-6B_status', 'COMPLETE',
            '8H-6A-6B_component', 'Manifest + Massive Downloader Integration',
            '8H-6A-6B_integration_test', 'PASS',
            '8H-6A_next', '8H-6A-6C',
            'historical_engine_status', 'DOWNLOADER_MANIFEST_INTEGRATED'
        ),
    updated_at = now()
from pmpd
where ps.strategy_id = pmpd.strategy_id;

commit;

select
    s.strategy_code,
    ps.active_phase_code,
    ps.active_phase_name,
    ps.next_phase_code,
    ps.next_phase_name,
    ps.metadata_json ->> '8H-6A-6B_status' as milestone_status,
    ps.metadata_json ->> '8H-6A_next' as next_implementation_step,
    ps.metadata_json ->> 'historical_engine_status' as historical_engine_status,
    ps.last_decision
from public.project_state ps
join public.strategies s
  on s.strategy_id = ps.strategy_id
where s.strategy_code = 'PMPD';

select
    pd.title,
    pd.status,
    pd.decision_date
from public.project_decisions pd
join public.strategies s
  on s.strategy_id = pd.strategy_id
where s.strategy_code = 'PMPD'
  and pd.title = '8H-6A-6B Manifest + Massive Downloader Integration completed';
