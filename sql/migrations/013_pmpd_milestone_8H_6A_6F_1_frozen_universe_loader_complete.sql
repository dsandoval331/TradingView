-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Milestone Update — 8H-6A-6F-1 Frozen Universe Batch Loader COMPLETE
-- Generated: 2026-08-28
--
-- Recommended repo location:
--   sql/migrations/013_pmpd_milestone_8H_6A_6F_1_frozen_universe_loader_complete.sql
--
-- VERIFIED EVIDENCE
--   Authoritative local source:
--     sql/migrations/2026-08-28_Migration_004_PMPD_112_Universe_Registration.sql
--
--   Loader validation:
--     Total members: 112
--     Unique symbols: 112
--     SET_1/2/3/4: 28 each
--     SET_1 #12: CVX
--     SET_4 #27: CVS
--     SET_1 first/last: MSFT / TQQQ
--     SET_4 first/last: ARM / NEE
--
--   SET_1 / 2025 preflight:
--     Exactly 28 partitions resolved in authoritative order.
--     No Massive API call or market-data download required.
--
-- SAFETY
--   * Does not create a second independent 112-symbol membership list.
--   * Keeps parent phase 8H-6 ACTIVE.
--   * Keeps 8H-7 as the next top-level phase.
--   * Sets next implementation step to 8H-6A-6F-2.
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
    '8H-6A-6F-1 Frozen Universe Batch Loader completed',
    'The historical acquisition platform now resolves PMPD_112_V1 from the existing authoritative version-controlled universe registration and validates its frozen membership before producing acquisition partitions.',
    'This prevents an independent Python copy of the 112-symbol universe from becoming a competing source of truth. The loader validates the full 4x28 structure and authoritative CVX/CVS correction before returning a selected set.',
    'Loader test PASS: 112 total, 112 unique, 28 members in each SET_1 through SET_4, SET_1 #12=CVX, SET_4 #27=CVS. SET_1/2025 read-only preflight PASS: exactly 28 partitions in authoritative order from MSFT through TQQQ.',
    'V4',
    jsonb_build_object(
        'milestone_code', '8H-6A-6F-1',
        'milestone_name', 'Frozen Universe Batch Loader',
        'milestone_status', 'COMPLETE',
        'universe_code', 'PMPD_112_V1',
        'authoritative_source',
            'sql/migrations/2026-08-28_Migration_004_PMPD_112_Universe_Registration.sql',
        'total_members', 112,
        'unique_symbols', 112,
        'set_count', 4,
        'members_per_set', 28,
        'set_1_position_12', 'CVX',
        'set_4_position_27', 'CVS',
        'set_1_2025_preflight_partitions', 28,
        'loader_validation', 'PASS',
        'preflight_validation', 'PASS',
        'network_activity_required', false,
        'completed_at', now()
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = '8H-6A-6F-1 Frozen Universe Batch Loader completed'
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
    last_decision = '8H-6A-6F-1 Frozen Universe Batch Loader passed; proceed to 8H-6A-6F-2 Universe-to-Acquisition Integration.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            '8H-6A-6F-1_status', 'COMPLETE',
            '8H-6A-6F-1_validation', 'PASS',
            'research_universe_code', 'PMPD_112_V1',
            'research_universe_local_loader', 'VALIDATED',
            'historical_engine_status', 'FROZEN_UNIVERSE_LOADER_PROVEN',
            '8H-6A_next', '8H-6A-6F-2'
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
  and pd.title = '8H-6A-6F-1 Frozen Universe Batch Loader completed';

select
    s.strategy_code,
    ps.active_phase_code,
    ps.next_phase_code,
    ps.metadata_json ->> '8H-6A-6F-1_status' as milestone_status,
    ps.metadata_json ->> 'research_universe_local_loader' as universe_loader_status,
    ps.metadata_json ->> 'historical_engine_status' as historical_engine_status,
    ps.metadata_json ->> '8H-6A_next' as next_implementation_step,
    ps.last_decision
from public.project_state ps
join public.strategies s
    on s.strategy_id = ps.strategy_id
where s.strategy_code = 'PMPD';
