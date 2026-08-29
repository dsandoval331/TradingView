-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Migration 004 — Register & Freeze PMPD_112_V1
-- Generated: 2026-08-28
--
-- PURPOSE
--   1) Populate authoritative four sets of 28 symbols (112 unique total).
--   2) Record the authoritative correction: Set 4 #27 = CVS (not CVX).
--   3) Validate 28 members per set and 112 unique total.
--   4) Freeze PMPD_112_V1 only if validation passes.
--   5) Update PM+PD project state so 8H-4G is the next readiness gate.
--
-- SAFETY
--   * Does not alter existing Second1M tables.
--   * Does not replace symbols silently.
--   * Raises an exception and aborts the transaction if the universe is invalid.
-- ============================================================================

begin;

-- ============================================================================
-- 1. CLEAR ONLY EXISTING MEMBERSHIP FOR THE DRAFT PMPD_112_V1
--
-- This migration is intended to register the authoritative membership.
-- The universe is currently draft and empty. This delete makes the migration
-- idempotent if re-run before or after a partial manual insert.
-- ============================================================================

delete from public.research_universe_members
where universe_id = (
    select universe_id
    from public.research_universes
    where universe_code = 'PMPD_112_V1'
);

-- ============================================================================
-- 2. INSERT AUTHORITATIVE 4 x 28 MEMBERSHIP
-- ============================================================================

with u as (
    select universe_id
    from public.research_universes
    where universe_code = 'PMPD_112_V1'
),
members(set_code, position_in_set, symbol) as (
    values
    -- SET_1
    ('SET_1', 1,  'MSFT'),
    ('SET_1', 2,  'GOOG'),
    ('SET_1', 3,  'AMZN'),
    ('SET_1', 4,  'PLTR'),
    ('SET_1', 5,  'TEAM'),
    ('SET_1', 6,  'META'),
    ('SET_1', 7,  'AAPL'),
    ('SET_1', 8,  'NFLX'),
    ('SET_1', 9,  'BAC'),
    ('SET_1', 10, 'LLY'),
    ('SET_1', 11, 'VRTX'),
    ('SET_1', 12, 'CVX'),
    ('SET_1', 13, 'AVGO'),
    ('SET_1', 14, 'INTC'),
    ('SET_1', 15, 'AMD'),
    ('SET_1', 16, 'NVDA'),
    ('SET_1', 17, 'TSLA'),
    ('SET_1', 18, 'TXN'),
    ('SET_1', 19, 'QCOM'),
    ('SET_1', 20, 'ORCL'),
    ('SET_1', 21, 'AMAT'),
    ('SET_1', 22, 'DELL'),
    ('SET_1', 23, 'IBM'),
    ('SET_1', 24, 'COIN'),
    ('SET_1', 25, 'SPY'),
    ('SET_1', 26, 'QQQ'),
    ('SET_1', 27, 'IWM'),
    ('SET_1', 28, 'TQQQ'),

    -- SET_2
    ('SET_2', 1,  'JNJ'),
    ('SET_2', 2,  'ADBE'),
    ('SET_2', 3,  'CMCSA'),
    ('SET_2', 4,  'SLB'),
    ('SET_2', 5,  'MRNA'),
    ('SET_2', 6,  'JPM'),
    ('SET_2', 7,  'GS'),
    ('SET_2', 8,  'V'),
    ('SET_2', 9,  'MA'),
    ('SET_2', 10, 'XOM'),
    ('SET_2', 11, 'COP'),
    ('SET_2', 12, 'CAT'),
    ('SET_2', 13, 'BA'),
    ('SET_2', 14, 'GE'),
    ('SET_2', 15, 'RTX'),
    ('SET_2', 16, 'WMT'),
    ('SET_2', 17, 'COST'),
    ('SET_2', 18, 'HD'),
    ('SET_2', 19, 'MCD'),
    ('SET_2', 20, 'DIS'),
    ('SET_2', 21, 'CRM'),
    ('SET_2', 22, 'MU'),
    ('SET_2', 23, 'UBER'),
    ('SET_2', 24, 'UNH'),
    ('SET_2', 25, 'ABBV'),
    ('SET_2', 26, 'TMO'),
    ('SET_2', 27, 'DDOG'),
    ('SET_2', 28, 'MNDY'),

    -- SET_3
    ('SET_3', 1,  'PANW'),
    ('SET_3', 2,  'CRWD'),
    ('SET_3', 3,  'NOW'),
    ('SET_3', 4,  'SNOW'),
    ('SET_3', 5,  'MRVL'),
    ('SET_3', 6,  'KLAC'),
    ('SET_3', 7,  'C'),
    ('SET_3', 8,  'MS'),
    ('SET_3', 9,  'AXP'),
    ('SET_3', 10, 'SCHW'),
    ('SET_3', 11, 'OXY'),
    ('SET_3', 12, 'EOG'),
    ('SET_3', 13, 'DE'),
    ('SET_3', 14, 'HON'),
    ('SET_3', 15, 'LMT'),
    ('SET_3', 16, 'FDX'),
    ('SET_3', 17, 'TGT'),
    ('SET_3', 18, 'LOW'),
    ('SET_3', 19, 'SBUX'),
    ('SET_3', 20, 'NKE'),
    ('SET_3', 21, 'PEP'),
    ('SET_3', 22, 'MRK'),
    ('SET_3', 23, 'PFE'),
    ('SET_3', 24, 'GILD'),
    ('SET_3', 25, 'ISRG'),
    ('SET_3', 26, 'T'),
    ('SET_3', 27, 'VZ'),
    ('SET_3', 28, 'BKNG'),

    -- SET_4
    ('SET_4', 1,  'ARM'),
    ('SET_4', 2,  'ASML'),
    ('SET_4', 3,  'LRCX'),
    ('SET_4', 4,  'ANET'),
    ('SET_4', 5,  'APP'),
    ('SET_4', 6,  'SHOP'),
    ('SET_4', 7,  'PYPL'),
    ('SET_4', 8,  'HOOD'),
    ('SET_4', 9,  'ABNB'),
    ('SET_4', 10, 'DASH'),
    ('SET_4', 11, 'RBLX'),
    ('SET_4', 12, 'LULU'),
    ('SET_4', 13, 'CMG'),
    ('SET_4', 14, 'TMUS'),
    ('SET_4', 15, 'CSCO'),
    ('SET_4', 16, 'BLK'),
    ('SET_4', 17, 'CME'),
    ('SET_4', 18, 'AXON'),
    ('SET_4', 19, 'ETN'),
    ('SET_4', 20, 'UPS'),
    ('SET_4', 21, 'URI'),
    ('SET_4', 22, 'CEG'),
    ('SET_4', 23, 'HAL'),
    ('SET_4', 24, 'AMGN'),
    ('SET_4', 25, 'REGN'),
    ('SET_4', 26, 'BMY'),
    ('SET_4', 27, 'CVS'),
    ('SET_4', 28, 'NEE')
)
insert into public.research_universe_members (
    universe_id,
    set_code,
    symbol,
    included,
    inclusion_reason,
    coverage_status,
    metadata_json
)
select
    u.universe_id,
    m.set_code,
    m.symbol,
    true,
    'Authoritative PMPD_112_V1 research-universe membership.',
    'NOT_ASSESSED',
    jsonb_build_object(
        'position_in_set', m.position_in_set,
        'source', 'authoritative_4x28_list'
    )
from u
cross join members m;

-- ============================================================================
-- 3. VALIDATE MEMBERSHIP
-- ============================================================================

do $$
declare
    v_universe_id uuid;
    v_total integer;
    v_unique integer;
    v_set1 integer;
    v_set2 integer;
    v_set3 integer;
    v_set4 integer;
begin
    select universe_id
      into v_universe_id
    from public.research_universes
    where universe_code = 'PMPD_112_V1';

    if v_universe_id is null then
        raise exception 'PMPD_112_V1 universe not found.';
    end if;

    select
        count(*) filter (where included),
        count(distinct symbol) filter (where included),
        count(*) filter (where included and set_code = 'SET_1'),
        count(*) filter (where included and set_code = 'SET_2'),
        count(*) filter (where included and set_code = 'SET_3'),
        count(*) filter (where included and set_code = 'SET_4')
    into
        v_total,
        v_unique,
        v_set1,
        v_set2,
        v_set3,
        v_set4
    from public.research_universe_members
    where universe_id = v_universe_id;

    if v_total <> 112 then
        raise exception 'Universe validation failed: expected 112 included members, found %.', v_total;
    end if;

    if v_unique <> 112 then
        raise exception 'Universe validation failed: expected 112 unique symbols, found %.', v_unique;
    end if;

    if v_set1 <> 28 or v_set2 <> 28 or v_set3 <> 28 or v_set4 <> 28 then
        raise exception
            'Universe validation failed: expected 28 symbols per set. Found SET_1 %, SET_2 %, SET_3 %, SET_4 %.',
            v_set1, v_set2, v_set3, v_set4;
    end if;
end $$;

-- ============================================================================
-- 4. FREEZE PMPD_112_V1
-- ============================================================================

update public.research_universes
set
    status = 'frozen',
    is_frozen = true,
    frozen_at = coalesce(frozen_at, now()),
    description =
        'Authoritative PM+PD 112-stock historical research universe: four sets of 28 unique symbols.',
    metadata_json =
        coalesce(metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            'set_count', 4,
            'members_per_set', 28,
            'member_count', 112,
            'unique_symbol_count', 112,
            'membership_status', 'VALIDATED_AND_FROZEN',
            'set4_position27', 'CVS'
        ),
    updated_at = now()
where universe_code = 'PMPD_112_V1';

-- ============================================================================
-- 5. RECORD AUTHORITATIVE CVX/CVS CORRECTION
-- ============================================================================

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
    'PMPD_112_V1 Set 4 ticker correction',
    'Set 4 position 27 is CVS. Set 1 position 12 remains CVX.',
    'The source screenshot appeared to show CVX in both sets; the user confirmed the authoritative Set 4 symbol is CVS.',
    'Authoritative universe clarification on 2026-08-28.',
    'V4',
    jsonb_build_object(
        'set_1_position_12', 'CVX',
        'set_4_position_27', 'CVS'
    )
from pmpd
where not exists (
    select 1
    from public.project_decisions d
    where d.strategy_id = pmpd.strategy_id
      and d.title = 'PMPD_112_V1 Set 4 ticker correction'
      and d.status = 'active'
);

-- ============================================================================
-- 6. UPDATE PM+PD PROJECT STATE
--
-- 8H-4 remains ACTIVE until the architecture readiness review (8H-4G).
-- ============================================================================

with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
update public.project_state ps
set
    active_phase_code = '8H-4',
    active_phase_name = 'Historical Data Architecture',
    next_phase_code = '8H-5',
    next_phase_name = 'Frozen V4 Parity Specification',
    blocker_count = 0,
    historical_dataset_status = 'UNIVERSE_FROZEN_ARCHITECTURE_REVIEW_PENDING',
    last_decision = 'PMPD_112_V1 registered and frozen: 4 sets x 28 = 112 unique symbols. 8H-4G readiness review remains.',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            'research_universe_code', 'PMPD_112_V1',
            'research_universe_membership', 'VALIDATED_AND_FROZEN',
            'research_universe_member_count', 112,
            'research_universe_set_count', 4,
            'historical_architecture_status', 'READINESS_REVIEW_PENDING'
        ),
    updated_at = now()
from pmpd
where ps.strategy_id = pmpd.strategy_id;

commit;

-- ============================================================================
-- 7. POST-MIGRATION VALIDATION QUERY
-- ============================================================================

select
    u.universe_code,
    u.status,
    u.is_frozen,
    u.expected_member_count,
    count(m.universe_member_id) filter (where m.included) as included_members,
    count(distinct m.symbol) filter (where m.included) as unique_symbols,
    count(*) filter (where m.included and m.set_code = 'SET_1') as set_1_count,
    count(*) filter (where m.included and m.set_code = 'SET_2') as set_2_count,
    count(*) filter (where m.included and m.set_code = 'SET_3') as set_3_count,
    count(*) filter (where m.included and m.set_code = 'SET_4') as set_4_count
from public.research_universes u
left join public.research_universe_members m
    on m.universe_id = u.universe_id
where u.universe_code = 'PMPD_112_V1'
group by
    u.universe_id,
    u.universe_code,
    u.status,
    u.is_frozen,
    u.expected_member_count;
