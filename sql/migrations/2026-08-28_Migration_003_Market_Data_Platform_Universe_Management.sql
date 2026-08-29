-- ============================================================================
-- TRADING RESEARCH PLATFORM
-- Migration 003 — Market Data Platform + Universe Management
-- Generated: 2026-08-28
--
-- PURPOSE
--   1) Add versioned research-universe management.
--   2) Add local MARKET_CACHE_V1 manifest / coverage metadata to Supabase.
--   3) Add persistent market-data quality issue tracking.
--   4) Register PLATFORM MD-1 ... MD-6 workstream.
--   5) Persist frozen 8H-4 architecture decisions.
--   6) Advance PM+PD project state from 8H-3 -> 8H-4.
--
-- SAFETY
--   * Does NOT drop or alter existing Second1M research tables.
--   * Does NOT store raw 1-minute market bars in Supabase.
--   * Does NOT invent/populate the PMPD_112_V1 ticker membership.
--   * Designed to be idempotent where practical.
-- ============================================================================

create extension if not exists pgcrypto;

-- ============================================================================
-- 1. VERSIONED RESEARCH UNIVERSES
-- ============================================================================

create table if not exists public.research_universes (
    universe_id uuid primary key default gen_random_uuid(),
    strategy_id uuid references public.strategies(strategy_id) on delete restrict,

    universe_code text not null unique,
    universe_name text not null,
    universe_version text not null,

    universe_type text not null default 'research'
        check (universe_type in ('research','context','validation','holdout','platform')),

    expected_member_count integer
        check (expected_member_count is null or expected_member_count >= 0),

    status text not null default 'draft'
        check (status in ('draft','active','frozen','retired')),

    is_frozen boolean not null default false,
    frozen_at timestamptz,

    description text,
    metadata_json jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    unique(strategy_id, universe_name, universe_version)
);

drop trigger if exists trg_research_universes_updated_at
    on public.research_universes;

create trigger trg_research_universes_updated_at
before update on public.research_universes
for each row execute function public.trp_set_updated_at();

create index if not exists idx_research_universes_strategy
    on public.research_universes(strategy_id);

-- ============================================================================
-- 2. UNIVERSE MEMBERS
-- ============================================================================

create table if not exists public.research_universe_members (
    universe_member_id uuid primary key default gen_random_uuid(),
    universe_id uuid not null
        references public.research_universes(universe_id) on delete cascade,

    set_code text,
    symbol text not null,

    included boolean not null default true,
    inclusion_reason text,

    active boolean not null default true,

    first_available_date date,
    last_available_date date,

    coverage_status text
        check (
            coverage_status is null or
            coverage_status in (
                'NOT_ASSESSED',
                'FULL',
                'PARTIAL_VALID',
                'LIMITED',
                'FAILED',
                'EXCLUDED'
            )
        ),

    notes text,
    metadata_json jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    unique(universe_id, symbol)
);

drop trigger if exists trg_research_universe_members_updated_at
    on public.research_universe_members;

create trigger trg_research_universe_members_updated_at
before update on public.research_universe_members
for each row execute function public.trp_set_updated_at();

create index if not exists idx_research_universe_members_universe_set
    on public.research_universe_members(universe_id, set_code);

create index if not exists idx_research_universe_members_symbol
    on public.research_universe_members(symbol);

-- ============================================================================
-- 3. LOCAL MARKET CACHE PARTITION MANIFEST
--
-- One row represents one local canonical cache partition, normally:
--     symbol x year x timeframe x cache_version
--
-- Raw Parquet files remain LOCAL. Supabase stores only metadata/inventory.
-- ============================================================================

create table if not exists public.market_cache_partitions (
    partition_id uuid primary key default gen_random_uuid(),

    symbol text not null,
    partition_year integer not null
        check (partition_year between 1900 and 2200),

    timeframe text not null default '1m',
    source text not null default 'MASSIVE',
    adjusted boolean not null default true,
    cache_version text not null default 'MARKET_CACHE_V1',

    local_relative_path text not null,

    requested_start date,
    requested_end date,

    actual_first_bar timestamptz,
    actual_last_bar timestamptz,

    row_count bigint not null default 0
        check (row_count >= 0),

    trading_days integer not null default 0
        check (trading_days >= 0),

    rth_days integer not null default 0
        check (rth_days >= 0),

    premarket_days integer not null default 0
        check (premarket_days >= 0),

    afterhours_days integer not null default 0
        check (afterhours_days >= 0),

    duplicate_count bigint not null default 0
        check (duplicate_count >= 0),

    conflicting_duplicate_count bigint not null default 0
        check (conflicting_duplicate_count >= 0),

    invalid_ohlc_count bigint not null default 0
        check (invalid_ohlc_count >= 0),

    missing_rth_minutes bigint not null default 0
        check (missing_rth_minutes >= 0),

    download_status text not null default 'NOT_REQUESTED'
        check (
            download_status in (
                'NOT_REQUESTED',
                'PARTIAL',
                'DOWNLOADED',
                'FAILED'
            )
        ),

    validation_status text not null default 'NOT_VALIDATED'
        check (
            validation_status in (
                'NOT_VALIDATED',
                'PASS',
                'PASS_WITH_WARNINGS',
                'FAIL'
            )
        ),

    download_attempts integer not null default 0
        check (download_attempts >= 0),

    last_download_at timestamptz,
    last_validated_at timestamptz,

    file_size_bytes bigint
        check (file_size_bytes is null or file_size_bytes >= 0),

    file_hash text,
    hash_algorithm text default 'SHA256',

    source_request_metadata jsonb not null default '{}'::jsonb,
    notes text,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    unique(symbol, partition_year, timeframe, source, adjusted, cache_version)
);

drop trigger if exists trg_market_cache_partitions_updated_at
    on public.market_cache_partitions;

create trigger trg_market_cache_partitions_updated_at
before update on public.market_cache_partitions
for each row execute function public.trp_set_updated_at();

create index if not exists idx_market_cache_partitions_status
    on public.market_cache_partitions(download_status, validation_status);

create index if not exists idx_market_cache_partitions_symbol
    on public.market_cache_partitions(symbol, partition_year);

-- ============================================================================
-- 4. PER-SYMBOL HISTORICAL COVERAGE
-- ============================================================================

create table if not exists public.market_data_coverage (
    coverage_id uuid primary key default gen_random_uuid(),

    universe_id uuid
        references public.research_universes(universe_id) on delete cascade,

    symbol text not null,

    source text not null default 'MASSIVE',
    timeframe text not null default '1m',
    cache_version text not null default 'MARKET_CACHE_V1',

    requested_start date,
    requested_end date,

    actual_first_bar timestamptz,
    actual_last_bar timestamptz,

    first_valid_rth_date date,
    last_valid_rth_date date,

    trading_days integer not null default 0
        check (trading_days >= 0),

    valid_premarket_days integer not null default 0
        check (valid_premarket_days >= 0),

    valid_rth_days integer not null default 0
        check (valid_rth_days >= 0),

    valid_pm_prev_rth_days integer not null default 0
        check (valid_pm_prev_rth_days >= 0),

    signal_capable_days integer not null default 0
        check (signal_capable_days >= 0),

    missing_or_invalid_sessions integer not null default 0
        check (missing_or_invalid_sessions >= 0),

    usable_pct numeric,

    coverage_status text not null default 'NOT_ASSESSED'
        check (
            coverage_status in (
                'NOT_ASSESSED',
                'FULL',
                'PARTIAL_VALID',
                'LIMITED',
                'FAILED',
                'EXCLUDED'
            )
        ),

    validation_status text not null default 'NOT_VALIDATED'
        check (
            validation_status in (
                'NOT_VALIDATED',
                'PASS',
                'PASS_WITH_WARNINGS',
                'FAIL'
            )
        ),

    exclusion_reason text,
    notes text,
    metadata_json jsonb not null default '{}'::jsonb,

    calculated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    unique(universe_id, symbol, source, timeframe, cache_version)
);

drop trigger if exists trg_market_data_coverage_updated_at
    on public.market_data_coverage;

create trigger trg_market_data_coverage_updated_at
before update on public.market_data_coverage
for each row execute function public.trp_set_updated_at();

create index if not exists idx_market_data_coverage_universe
    on public.market_data_coverage(universe_id, coverage_status);

create index if not exists idx_market_data_coverage_symbol
    on public.market_data_coverage(symbol);

-- ============================================================================
-- 5. MARKET DATA QUALITY ISSUE LOG
-- ============================================================================

create table if not exists public.market_data_quality_issues (
    issue_id uuid primary key default gen_random_uuid(),

    partition_id uuid
        references public.market_cache_partitions(partition_id) on delete cascade,

    universe_id uuid
        references public.research_universes(universe_id) on delete set null,

    symbol text not null,
    trade_date date,
    timestamp_utc timestamptz,

    issue_type text not null,
    severity text not null
        check (severity in ('INFO','WARNING','ERROR','CRITICAL')),

    issue_count integer not null default 1
        check (issue_count > 0),

    description text,
    observed_value jsonb,
    expected_value jsonb,

    resolution_status text not null default 'OPEN'
        check (
            resolution_status in (
                'OPEN',
                'ACCEPTED',
                'RESOLVED',
                'IGNORED'
            )
        ),

    resolution_notes text,

    detected_at timestamptz not null default now(),
    resolved_at timestamptz,

    metadata_json jsonb not null default '{}'::jsonb
);

create index if not exists idx_market_data_quality_issues_symbol_date
    on public.market_data_quality_issues(symbol, trade_date);

create index if not exists idx_market_data_quality_issues_open
    on public.market_data_quality_issues(resolution_status, severity);

-- ============================================================================
-- 6. REGISTER DRAFT UNIVERSES
--
-- PMPD_112_V1 is intentionally EMPTY after this migration.
-- Authoritative 4 x 28 membership is populated only in 8H-4F.
-- ============================================================================

with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
insert into public.research_universes (
    strategy_id,
    universe_code,
    universe_name,
    universe_version,
    universe_type,
    expected_member_count,
    status,
    is_frozen,
    description,
    metadata_json
)
select
    strategy_id,
    'PMPD_112_V1',
    'PM+PD 112-Stock Historical Research Universe',
    'V1',
    'research',
    112,
    'draft',
    false,
    'Four authoritative sets of 28 PM+PD research stocks. Membership intentionally deferred to 8H-4F.',
    jsonb_build_object(
        'set_count', 4,
        'members_per_set', 28,
        'membership_status', 'PENDING_AUTHORITATIVE_LIST'
    )
from pmpd
on conflict (universe_code) do update
set
    universe_name = excluded.universe_name,
    expected_member_count = excluded.expected_member_count,
    description = excluded.description,
    updated_at = now();

with platform as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PLATFORM'
)
insert into public.research_universes (
    strategy_id,
    universe_code,
    universe_name,
    universe_version,
    universe_type,
    expected_member_count,
    status,
    is_frozen,
    description,
    metadata_json
)
select
    strategy_id,
    'MARKET_CONTEXT_V1',
    'Market Context Universe',
    'V1',
    'context',
    3,
    'active',
    false,
    'Initial broad-market context instruments used by PM+PD research.',
    jsonb_build_object(
        'purpose', 'market_bias',
        'initial_symbols', jsonb_build_array('SPY','QQQ','DIA')
    )
from platform
on conflict (universe_code) do update
set
    universe_name = excluded.universe_name,
    expected_member_count = excluded.expected_member_count,
    description = excluded.description,
    metadata_json = excluded.metadata_json,
    updated_at = now();

-- Context universe membership is known and may be seeded now.
with u as (
    select universe_id
    from public.research_universes
    where universe_code = 'MARKET_CONTEXT_V1'
)
insert into public.research_universe_members (
    universe_id,
    set_code,
    symbol,
    included,
    inclusion_reason,
    coverage_status
)
select
    u.universe_id,
    'CONTEXT',
    v.symbol,
    true,
    'Broad-market context instrument for market-bias research.',
    'NOT_ASSESSED'
from u
cross join (
    values ('SPY'), ('QQQ'), ('DIA')
) as v(symbol)
on conflict (universe_id, symbol) do nothing;

-- ============================================================================
-- 7. PLATFORM MARKET DATA WORKSTREAM
-- ============================================================================

with platform as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PLATFORM'
)
insert into public.program_phases (
    strategy_id,
    phase_code,
    phase_name,
    objective,
    status,
    sequence_order,
    exit_criteria,
    next_phase_code
)
select
    strategy_id,
    phase_code,
    phase_name,
    objective,
    status,
    sequence_order,
    exit_criteria,
    next_phase_code
from platform
cross join (
    values
    (
        'MD-1',
        'Canonical Cache Specification',
        'Freeze MARKET_CACHE_V1 raw 1-minute storage, timestamp, session, partition, and reproducibility rules.',
        'complete',
        101,
        'Canonical 1-minute cache contract approved.',
        'MD-2'
    ),
    (
        'MD-2',
        'Massive Downloader',
        'Build a rate-limited, paginated Massive REST aggregate downloader.',
        'ready',
        102,
        'Downloader reliably retrieves requested 1-minute history.',
        'MD-3'
    ),
    (
        'MD-3',
        'Manifest / Resume Engine',
        'Track local partitions and resume interrupted historical acquisition without redundant downloads.',
        'backlog',
        103,
        'Downloader resumes from manifest state and avoids unnecessary redownloads.',
        'MD-4'
    ),
    (
        'MD-4',
        'Data Quality Validator',
        'Validate canonical bars, sessions, duplicates, OHLC integrity, coverage, and daily reconciliation.',
        'backlog',
        104,
        'Quality checks and persistent issue logging operational.',
        'MD-5'
    ),
    (
        'MD-5',
        'Generic Timeframe Resampler',
        'Produce deterministic 2m/3m/5m/10m/15m bars from canonical 1-minute data.',
        'backlog',
        105,
        'Resampled bars follow frozen New York session boundaries and pass parity fixtures.',
        'MD-6'
    ),
    (
        'MD-6',
        'Cache Coverage Report',
        'Produce symbol/year and universe-level historical coverage/readiness reporting.',
        'backlog',
        106,
        'Coverage report identifies research-ready and deficient symbols/sessions.',
        null
    )
) as v(
    phase_code,
    phase_name,
    objective,
    status,
    sequence_order,
    exit_criteria,
    next_phase_code
)
on conflict (strategy_id, phase_code) do update
set
    phase_name = excluded.phase_name,
    objective = excluded.objective,
    status = excluded.status,
    sequence_order = excluded.sequence_order,
    exit_criteria = excluded.exit_criteria,
    next_phase_code = excluded.next_phase_code,
    updated_at = now();

-- ============================================================================
-- 8. PLATFORM CURRENT STATE
-- ============================================================================

with platform as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PLATFORM'
)
insert into public.project_state (
    strategy_id,
    active_phase_code,
    active_phase_name,
    next_phase_code,
    next_phase_name,
    blocker_count,
    baseline_status,
    historical_dataset_status,
    active_tangent_count,
    last_decision,
    roadmap_version,
    metadata_json
)
select
    strategy_id,
    'MD-2',
    'Massive Downloader',
    'MD-3',
    'Manifest / Resume Engine',
    0,
    'MARKET_CACHE_V1_FROZEN',
    'NOT_BUILT',
    0,
    'Canonical 1-minute Massive data will be cached locally as Parquet and reused across strategies.',
    'MARKET-DATA-RM-1.0',
    jsonb_build_object(
        'cache_version', 'MARKET_CACHE_V1',
        'canonical_timeframe', '1m',
        'timezone', 'America/New_York',
        'source', 'MASSIVE',
        'adjusted', true,
        'storage', 'LOCAL_PARQUET',
        'partitioning', 'SYMBOL_YEAR'
    )
from platform
on conflict (strategy_id) do update
set
    active_phase_code = excluded.active_phase_code,
    active_phase_name = excluded.active_phase_name,
    next_phase_code = excluded.next_phase_code,
    next_phase_name = excluded.next_phase_name,
    blocker_count = excluded.blocker_count,
    baseline_status = excluded.baseline_status,
    historical_dataset_status = excluded.historical_dataset_status,
    active_tangent_count = excluded.active_tangent_count,
    last_decision = excluded.last_decision,
    roadmap_version = excluded.roadmap_version,
    metadata_json = excluded.metadata_json,
    updated_at = now();

-- ============================================================================
-- 9. PERSIST 8H-4 ARCHITECTURE DECISIONS
--
-- Guarded by title to avoid duplicate decision rows if migration is re-run.
-- ============================================================================

with platform as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PLATFORM'
),
decision_rows(title, decision, rationale, evidence) as (
    values
    (
        'MARKET_CACHE_V1 canonical resolution',
        'Canonical historical intraday market data will be retained at 1-minute resolution.',
        'Higher timeframes can be deterministically reconstructed from a single reusable source.',
        '8H-4A/4B architecture.'
    ),
    (
        'Local Parquet raw cache',
        'Raw 1-minute historical bars will remain in a local Parquet cache initially; Supabase stores metadata and derived research results.',
        'Avoids unnecessary database volume while preserving reusable raw history.',
        '8H-4A/4B architecture.'
    ),
    (
        'Symbol-year partitioning',
        'MARKET_CACHE_V1 files are partitioned by symbol and calendar year.',
        'Balances file size, manageability, incremental updates, and reuse.',
        '8H-4B architecture.'
    ),
    (
        'New York session rules',
        'Canonical sessions use America/New_York: PRE 04:00-09:29, RTH 09:30-15:59, AH 16:00-19:59.',
        'Matches U.S. equity session logic while handling DST automatically.',
        '8H-4B architecture.'
    ),
    (
        'Derived levels stay outside raw cache',
        'PMH/PML/PDH/PDL and strategy indicators are derived from canonical bars and are not embedded in raw MARKET_CACHE_V1 rows.',
        'Keeps raw market data strategy-agnostic and reusable.',
        '8H-4A/4B architecture.'
    ),
    (
        'Incremental resumable acquisition',
        'Historical acquisition must be incremental, paginated, rate-limited, retryable, and resumable.',
        'Supports Massive free-plan constraints and prevents redundant acquisition.',
        '8H-4C architecture.'
    ),
    (
        'TradingView parity role',
        'TradingView is the frozen V4 parity/reference implementation; Massive is the bulk historical market-data source.',
        'Separates signal-definition parity from historical data acquisition.',
        '8H-4C architecture.'
    ),
    (
        'Versioned immutable research universes',
        'Formal research universes are versioned and frozen before experiments; membership is never silently replaced.',
        'Preserves experiment reproducibility and cohort integrity.',
        '8H-4D architecture.'
    ),
    (
        'Coverage is factor-specific',
        'Short-history symbols are not automatically removed; eligibility depends on the history required by each factor or experiment.',
        'Prevents unnecessary sample loss while preserving valid lookback requirements.',
        '8H-4D architecture.'
    )
)
insert into public.project_decisions (
    strategy_id,
    title,
    decision,
    rationale,
    evidence
)
select
    platform.strategy_id,
    d.title,
    d.decision,
    d.rationale,
    d.evidence
from platform
cross join decision_rows d
where not exists (
    select 1
    from public.project_decisions existing
    where existing.strategy_id = platform.strategy_id
      and existing.title = d.title
      and existing.status = 'active'
);

-- PM+PD-specific universe decision.
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
    affects_model_version
)
select
    pmpd.strategy_id,
    'PMPD_112_V1 universe definition',
    'The initial PM+PD historical research universe is four authoritative sets of 28 stocks (112 unique symbols); exact membership must be recovered before the universe is frozen.',
    'The four-set identity supports cohort robustness testing and prevents accidental replacement of the original research population.',
    '8H-4D universe specification.',
    'V4'
from pmpd
where not exists (
    select 1
    from public.project_decisions existing
    where existing.strategy_id = pmpd.strategy_id
      and existing.title = 'PMPD_112_V1 universe definition'
      and existing.status = 'active'
);

-- ============================================================================
-- 10. ADVANCE PM+PD ROADMAP STATE
-- ============================================================================

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
  and pp.phase_code = '8H-3';

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
  and pp.phase_code = '8H-4';

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
    historical_dataset_status = 'ARCHITECTURE_IN_PROGRESS',
    last_decision = 'MARKET_CACHE_V1 + PMPD_112_V1 historical architecture approved; authoritative 4x28 membership remains to be registered.',
    roadmap_version = 'PMPD-RM-1.0',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            'cache_version', 'MARKET_CACHE_V1',
            'research_universe_code', 'PMPD_112_V1',
            'research_universe_membership', 'PENDING',
            'context_universe_code', 'MARKET_CONTEXT_V1',
            'historical_architecture_status', 'ACTIVE'
        ),
    updated_at = now()
from pmpd
where ps.strategy_id = pmpd.strategy_id;

-- ============================================================================
-- 11. RLS
-- ============================================================================

alter table public.research_universes enable row level security;
alter table public.research_universe_members enable row level security;
alter table public.market_cache_partitions enable row level security;
alter table public.market_data_coverage enable row level security;
alter table public.market_data_quality_issues enable row level security;

-- No anon/public policies are created.

-- ============================================================================
-- 12. CONVENIENCE VIEW — UNIVERSE READINESS
-- ============================================================================

create or replace view public.v_research_universe_readiness as
select
    u.universe_code,
    u.universe_name,
    u.universe_version,
    u.universe_type,
    u.status,
    u.is_frozen,
    u.expected_member_count,

    count(m.universe_member_id) filter (where m.included) as included_members,
    count(distinct m.set_code) filter (where m.included) as included_sets,

    count(m.universe_member_id)
        filter (where m.included and m.coverage_status = 'FULL') as full_coverage_members,

    count(m.universe_member_id)
        filter (
            where m.included
              and m.coverage_status in ('FULL','PARTIAL_VALID')
        ) as research_usable_members,

    case
        when count(m.universe_member_id) filter (where m.included)
             = u.expected_member_count
        then true
        else false
    end as member_count_matches_expected

from public.research_universes u
left join public.research_universe_members m
    on m.universe_id = u.universe_id
group by
    u.universe_id,
    u.universe_code,
    u.universe_name,
    u.universe_version,
    u.universe_type,
    u.status,
    u.is_frozen,
    u.expected_member_count;

-- ============================================================================
-- END MIGRATION 003
-- ============================================================================
