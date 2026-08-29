-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Milestone Update — 8H-6A-6C Production Symbol/Year Acquisition COMPLETE
-- Generated: 2026-08-28
--
-- Recommended repo location:
--   sql/migrations/010_pmpd_milestone_8H_6A_6C_production_symbol_year_complete.sql
--
-- PURPOSE
--   Record completion of implementation milestone 8H-6A-6C while keeping
--   top-level phase 8H-6 Historical Engine & Ingestion ACTIVE.
--
-- VERIFIED EVIDENCE
--   AAPL 2025 production partition:
--     - First run action = DOWNLOADED
--     - Requested range = 2025-01-01 through 2025-12-31
--     - Rows = 188,072
--     - Unique timestamps = 188,072
--     - Trading days = 250
--     - RTH days = 250
--     - Premarket days = 250
--     - After-hours days = 250
--     - Manifest download_status = DOWNLOADED
--     - Manifest validation_status = PASS
--     - SHA-256 present
--     - Second run action = SKIPPED_COMPLETE
--     - Download attempts remained = 1
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
    '8H-6A-6C Production Symbol/Year Acquisition completed',
    'The production MARKET_CACHE_V1 symbol/year acquisition flow passed on AAPL 2025, including full-year download, canonical validation, atomic Parquet write, manifest persistence, file hashing, and repeat-run skip behavior.',
    'This proves the production partition workflow can safely create and preserve a real symbol/year cache partition before scaling to multi-partition acquisition.',
    'AAPL 2025 test passed on 2026-08-28: rows=188072; unique timestamps=188072; trading/rth/premarket/afterhours days=250; manifest=DOWNLOADED/PASS; repeat action=SKIPPED_COMPLETE; download_attempts remained 1.',
    'V4',
    jsonb_build_object(
        'milestone_code', '8H-6A-6C',
        'milestone_name', 'Production Symbol/Year Acquisition',
        'milestone_status', 'COMPLETE',
        'component', 'MARKET_CACHE_V1',
        'test_symbol', 'AAPL',
        'test_year', 2025,
        'row_count', 188072,
        'unique_timestamps', 188072,
        'trading_days', 250,
        'rth_days', 250,
        'premarket_days', 250,
        'afterhours_days', 250,
        'first_run_action', 'DOWNLOADED',
        'second_run_action', 'SKIPPED_COMPLETE',
        'validation_status', 'PASS',
        'download_attempts_after_skip', 1,
        'completed_at', now()
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = '8H-6A-6C Production Symbol/Year Acquisition completed'
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
    last_decision = '8H-6A-6C Production Symbol/Year Acquisition passed on AAPL 2025; proceed to 8H-6A-6D Controlled Multi-Partition Acquisition.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            '8H-6A-6C_status', 'COMPLETE',
            '8H-6A-6C_component', 'Production Symbol/Year Acquisition',
            '8H-6A-6C_test_symbol', 'AAPL',
            '8H-6A-6C_test_year', '2025',
            '8H-6A-6C_validation', 'PASS',
            '8H-6A_next', '8H-6A-6D',
            'historical_engine_status', 'PRODUCTION_SYMBOL_YEAR_ACQUISITION_PROVEN'
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
    ps.metadata_json ->> '8H-6A-6C_status' as milestone_status,
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
  and pd.title = '8H-6A-6C Production Symbol/Year Acquisition completed';
