-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Milestone Update — 8H-6A-6A Local Manifest Engine COMPLETE
-- Generated: 2026-08-28
--
-- Recommended repo location:
--   sql/migrations/008_pmpd_milestone_8H_6A_6A_manifest_complete.sql
--
-- PURPOSE
--   Record completion of implementation milestone 8H-6A-6A while keeping
--   top-level phase 8H-6 Historical Engine & Ingestion ACTIVE.
--
-- VERIFIED EVIDENCE
--   Local manifest smoke test passed:
--     - Manifest persisted successfully
--     - AAPL 2026 recognized as complete
--     - Next incomplete resolved as MSFT 2026
--     - SHA-256 hash length = 64
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
    '8H-6A-6A Local Manifest Engine completed',
    'The MARKET_CACHE_V1 local manifest engine passed its smoke test and is approved as the local partition-state foundation for resumable historical acquisition.',
    'Historical acquisition must recognize completed partitions, preserve file-integrity metadata, and resume from the next incomplete symbol/year before large-scale downloading begins.',
    'Smoke test passed on 2026-08-28: Rows=1; AAPL 2026 complete=True; next incomplete=(MSFT, 2026); SHA256 length=64.',
    'V4',
    jsonb_build_object(
        'milestone_code', '8H-6A-6A',
        'milestone_name', 'Local Manifest Engine',
        'milestone_status', 'COMPLETE',
        'component', 'MARKET_CACHE_V1',
        'manifest_version', 'MARKET_CACHE_MANIFEST_V1',
        'smoke_test_status', 'PASS',
        'completed_at', now()
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = '8H-6A-6A Local Manifest Engine completed'
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
    last_decision = '8H-6A-6A Local Manifest Engine smoke test passed; proceed to 8H-6A-6B Manifest + Massive Downloader Integration.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            '8H-6A-6A_status', 'COMPLETE',
            '8H-6A-6A_component', 'Local Manifest Engine',
            '8H-6A-6A_manifest_version', 'MARKET_CACHE_MANIFEST_V1',
            '8H-6A-6A_smoke_test', 'PASS',
            '8H-6A_next', '8H-6A-6B',
            'historical_engine_status', 'MANIFEST_ENGINE_COMPLETE'
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
    ps.metadata_json ->> '8H-6A-6A_status' as milestone_status,
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
  and pd.title = '8H-6A-6A Local Manifest Engine completed';
