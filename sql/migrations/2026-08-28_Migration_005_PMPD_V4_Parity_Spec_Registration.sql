-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Migration 005 — Register PMPD_V4_PARITY_SPEC_V1
-- Generated: 2026-08-28
--
-- Assumes Migration 002/003/004 have been applied.
-- Does not alter Second1M research tables.
-- ============================================================================

begin;

-- 1. Persist the frozen parity-spec decision.
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
    'PMPD V4 parity specification frozen',
    'Freeze PMPD_V4_PARITY_SPEC_V1 as the implementation contract for the external Massive/Python historical engine.',
    'Historical-engine development must reproduce the frozen TradingView V4 signal/classification/outcome methodology before expanded research begins.',
    '8H-5A through 8H-5D parity review completed 2026-08-28.',
    'V4',
    jsonb_build_object(
        'spec_code', 'PMPD_V4_PARITY_SPEC_V1',
        'spec_status', 'FROZEN',
        'signal_timeframe', '5m',
        'canonical_raw_timeframe', '1m',
        'timezone', 'America/New_York',
        'primary_favorable_pct', 0.50,
        'primary_adverse_pct', 0.50,
        'v4_same_bar_policy', 'BOTH_AMBIGUOUS',
        'signal_candle_excursion', 'EXCLUDED',
        'overnight_carry', false,
        'checkpoint_minutes', jsonb_build_array(1,2,3,5,10,15,30),
        'profile_precedence', jsonb_build_array(
            'Explosive',
            'Controlled Strong',
            'Efficient Moderate',
            'Delayed Strong',
            'Pretty but Weak',
            'Unclassified'
        )
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = 'PMPD V4 parity specification frozen'
      and d.status = 'active'
);

-- 2. Complete 8H-5.
with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
update public.program_phases pp
set
    status = 'complete',
    completed_at = coalesce(completed_at, now()),
    updated_at = now()
from pmpd
where pp.strategy_id = pmpd.strategy_id
  and pp.phase_code = '8H-5';

-- 3. Activate 8H-6.
with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
update public.program_phases pp
set
    status = 'active',
    started_at = coalesce(started_at, now()),
    updated_at = now()
from pmpd
where pp.strategy_id = pmpd.strategy_id
  and pp.phase_code = '8H-6';

-- 4. Update authoritative PM+PD project state.
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
    blocker_count = 0,
    baseline_model = 'V4',
    baseline_status = 'FROZEN_BASELINE',
    historical_dataset_status = 'ENGINE_IMPLEMENTATION_PENDING',
    last_decision = 'PMPD_V4_PARITY_SPEC_V1 frozen; external historical engine may now be implemented against the V4 contract.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            'parity_spec_code', 'PMPD_V4_PARITY_SPEC_V1',
            'parity_spec_status', 'FROZEN',
            'signal_timeframe', '5m',
            'canonical_raw_timeframe', '1m',
            'research_universe_code', 'PMPD_112_V1',
            'historical_engine_status', 'IMPLEMENTATION_PENDING'
        ),
    updated_at = now()
from pmpd
where ps.strategy_id = pmpd.strategy_id;

commit;

-- ============================================================================
-- POST-MIGRATION VALIDATION
-- ============================================================================

select
    s.strategy_code,
    ps.active_phase_code,
    ps.active_phase_name,
    ps.next_phase_code,
    ps.next_phase_name,
    ps.baseline_model,
    ps.baseline_status,
    ps.historical_dataset_status,
    ps.metadata_json ->> 'parity_spec_code' as parity_spec_code,
    ps.metadata_json ->> 'parity_spec_status' as parity_spec_status
from public.project_state ps
join public.strategies s
  on s.strategy_id = ps.strategy_id
where s.strategy_code = 'PMPD';

select
    pp.phase_code,
    pp.phase_name,
    pp.status
from public.program_phases pp
join public.strategies s
  on s.strategy_id = pp.strategy_id
where s.strategy_code = 'PMPD'
  and pp.phase_code in ('8H-4','8H-5','8H-6','8H-7')
order by pp.sequence_order;
