-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Milestone Update — 8H-6A-6D Controlled Multi-Partition Acquisition COMPLETE
-- Generated: 2026-08-28
--
-- Recommended repo location:
--   sql/migrations/011_pmpd_milestone_8H_6A_6D_controlled_multi_partition_complete.sql
--
-- VERIFIED EVIDENCE
-- First controlled batch:
--   AAPL 2025 -> SKIPPED_COMPLETE, 188072 rows
--   MSFT 2025 -> DOWNLOADED,       156075 rows
--   NVDA 2025 -> DOWNLOADED,       237805 rows
--   Total=3, Downloaded=2, Skipped=1, Failed=0
--
-- Repeat controlled batch:
--   AAPL 2025 -> SKIPPED_COMPLETE
--   MSFT 2025 -> SKIPPED_COMPLETE
--   NVDA 2025 -> SKIPPED_COMPLETE
--   Total=3, Downloaded=0, Skipped=3, Failed=0
--
-- OBSERVATION / FOLLOW-UP
--   The batch wrapper currently requests the Massive API key before it knows
--   whether every requested partition is already complete. This is not a
--   correctness or data-integrity failure. Record it as a non-blocking
--   implementation improvement before large-scale bootstrap.
--
-- SAFETY
--   * Keeps parent phase 8H-6 ACTIVE.
--   * Keeps 8H-7 as the next top-level phase.
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
    '8H-6A-6D Controlled Multi-Partition Acquisition completed',
    'Controlled multi-partition acquisition and repeat-run resume/skip behavior passed for AAPL, MSFT, and NVDA 2025.',
    'The production acquisition layer can safely orchestrate a batch containing both already-complete and new symbol/year partitions, preserve completed work, and skip all completed partitions on a repeat run.',
    'First run: AAPL SKIPPED_COMPLETE 188072 rows; MSFT DOWNLOADED 156075 rows; NVDA DOWNLOADED 237805 rows; total=3 downloaded=2 skipped=1 failed=0. Repeat run: all three SKIPPED_COMPLETE; total=3 downloaded=0 skipped=3 failed=0.',
    'V4',
    jsonb_build_object(
        'milestone_code', '8H-6A-6D',
        'milestone_name', 'Controlled Multi-Partition Acquisition',
        'milestone_status', 'COMPLETE',
        'batch_year', 2025,
        'symbols', jsonb_build_array('AAPL','MSFT','NVDA'),
        'first_run_downloaded', 2,
        'first_run_skipped', 1,
        'first_run_failed', 0,
        'repeat_run_downloaded', 0,
        'repeat_run_skipped', 3,
        'repeat_run_failed', 0,
        'aapl_rows', 188072,
        'msft_rows', 156075,
        'nvda_rows', 237805,
        'resume_skip_validation', 'PASS',
        'non_blocking_improvement',
            'Avoid requesting Massive API key when every requested partition is already complete.',
        'completed_at', now()
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = '8H-6A-6D Controlled Multi-Partition Acquisition completed'
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
    last_decision = '8H-6A-6D Controlled Multi-Partition Acquisition passed; continue 8H-6 acquisition hardening/scaling before 8H-7.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            '8H-6A-6D_status', 'COMPLETE',
            '8H-6A-6D_validation', 'PASS',
            '8H-6A-6D_symbols', jsonb_build_array('AAPL','MSFT','NVDA'),
            '8H-6A-6D_repeat_skip', 'PASS',
            'historical_engine_status', 'CONTROLLED_MULTI_PARTITION_PROVEN',
            'acquisition_non_blocking_improvement',
                'Defer Massive API-key prompt until at least one partition requires download.'
        ),
    updated_at = now()
from pmpd
where ps.strategy_id = pmpd.strategy_id;

commit;

-- Verification
select
    s.strategy_code,
    ps.active_phase_code,
    ps.active_phase_name,
    ps.next_phase_code,
    ps.next_phase_name,
    ps.metadata_json ->> '8H-6A-6D_status' as milestone_status,
    ps.metadata_json ->> '8H-6A-6D_validation' as validation_status,
    ps.metadata_json ->> 'historical_engine_status' as historical_engine_status,
    ps.metadata_json ->> 'acquisition_non_blocking_improvement' as non_blocking_improvement,
    ps.last_decision
from public.project_state ps
join public.strategies s on s.strategy_id = ps.strategy_id
where s.strategy_code = 'PMPD';

select
    pd.title,
    pd.status,
    pd.decision_date
from public.project_decisions pd
join public.strategies s on s.strategy_id = pd.strategy_id
where s.strategy_code = 'PMPD'
  and pd.title = '8H-6A-6D Controlled Multi-Partition Acquisition completed';
