-- Premarket Strategy Scanner PMS-3 Foundation V1
-- Backup copy of schema applied to Supabase project Pineview.
-- Created 2026-09-07/08 planning session.

create table if not exists public.pms_sector_mappings (
  mapping_id uuid primary key default gen_random_uuid(),
  symbol text not null,
  sector_code text,
  sector_name text,
  sector_benchmark_symbol text,
  industry_code text,
  industry_name text,
  industry_benchmark_symbol text,
  effective_from date not null,
  effective_to date,
  source text not null,
  mapping_version text not null,
  mapping_status text not null default 'VALID',
  confidence_status text,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint pms_sector_mappings_dates_ck check (effective_to is null or effective_to >= effective_from),
  constraint pms_sector_mappings_status_ck check (mapping_status in ('VALID','UNKNOWN','INVALID','REVIEW')),
  constraint pms_sector_mappings_unique_period unique (symbol, effective_from, mapping_version)
);

create index if not exists pms_sector_mappings_lookup_idx
  on public.pms_sector_mappings(symbol, effective_from, effective_to);

create table if not exists public.pms_snapshot_runs (
  snapshot_run_id uuid primary key default gen_random_uuid(),
  trade_date date not null,
  snapshot_code text not null,
  snapshot_asof timestamptz not null,
  timezone_name text not null default 'America/Chicago',
  candidate_universe_code text not null,
  candidate_universe_version text,
  factor_registry_version text not null,
  feature_contract_version text not null,
  snapshot_contract_version text not null,
  source_lineage_json jsonb not null default '{}'::jsonb,
  run_status text not null default 'CREATED',
  row_count integer,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint pms_snapshot_runs_code_ck check (snapshot_code in ('SCAN_A','SCAN_B')),
  constraint pms_snapshot_runs_status_ck check (run_status in ('CREATED','RUNNING','COMPLETE','PARTIAL','FAILED')),
  constraint pms_snapshot_runs_unique unique (
    trade_date, snapshot_code, candidate_universe_code,
    factor_registry_version, feature_contract_version
  )
);

create index if not exists pms_snapshot_runs_asof_idx
  on public.pms_snapshot_runs(snapshot_asof);

create table if not exists public.pms_snapshot_candidates (
  snapshot_candidate_id uuid primary key default gen_random_uuid(),
  snapshot_run_id uuid not null references public.pms_snapshot_runs(snapshot_run_id) on delete cascade,
  symbol text not null,
  strategy_family text not null,
  direction text not null,
  eligibility_state text not null,
  gate_state text,
  rank_position integer,
  composite_score numeric,
  raw_features_json jsonb not null default '{}'::jsonb,
  context_states_json jsonb not null default '{}'::jsonb,
  gate_results_json jsonb not null default '{}'::jsonb,
  missing_data_json jsonb not null default '{}'::jsonb,
  explanation_json jsonb not null default '{}'::jsonb,
  lineage_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint pms_snapshot_candidates_direction_ck check (direction in ('BULLISH','BEARISH')),
  constraint pms_snapshot_candidates_eligibility_ck check (
    eligibility_state in ('ELIGIBLE','NO_TRADE','INSUFFICIENT_DATA','EVENT_REGIME')
  ),
  constraint pms_snapshot_candidates_unique unique (
    snapshot_run_id, symbol, strategy_family, direction
  )
);

create index if not exists pms_snapshot_candidates_lookup_idx
  on public.pms_snapshot_candidates(snapshot_run_id, strategy_family, direction, rank_position);

create index if not exists pms_snapshot_candidates_symbol_idx
  on public.pms_snapshot_candidates(symbol, strategy_family, direction);

create table if not exists public.pms_snapshot_outcomes (
  snapshot_outcome_id uuid primary key default gen_random_uuid(),
  snapshot_candidate_id uuid not null references public.pms_snapshot_candidates(snapshot_candidate_id) on delete cascade,
  outcome_contract_version text not null,
  label_status text not null default 'PENDING',
  signal_occurred boolean,
  signal_timestamp timestamptz,
  favorable_050_before_adverse_050 boolean,
  favorable_100_before_adverse_050 boolean,
  mfe_pct numeric,
  mae_pct numeric,
  first_reached text,
  resolution_timestamp timestamptz,
  outcome_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint pms_snapshot_outcomes_status_ck check (
    label_status in ('PENDING','RESOLVED','UNRESOLVED','NOT_APPLICABLE','INVALID')
  ),
  constraint pms_snapshot_outcomes_first_reached_ck check (
    first_reached is null or first_reached in ('FAVORABLE','ADVERSE','NEITHER','TIE','UNKNOWN')
  ),
  constraint pms_snapshot_outcomes_unique unique (
    snapshot_candidate_id, outcome_contract_version
  )
);

alter table public.pms_sector_mappings enable row level security;
alter table public.pms_snapshot_runs enable row level security;
alter table public.pms_snapshot_candidates enable row level security;
alter table public.pms_snapshot_outcomes enable row level security;

revoke all on table public.pms_sector_mappings from anon, authenticated;
revoke all on table public.pms_snapshot_runs from anon, authenticated;
revoke all on table public.pms_snapshot_candidates from anon, authenticated;
revoke all on table public.pms_snapshot_outcomes from anon, authenticated;

grant select, insert, update, delete on table public.pms_sector_mappings to service_role;
grant select, insert, update, delete on table public.pms_snapshot_runs to service_role;
grant select, insert, update, delete on table public.pms_snapshot_candidates to service_role;
grant select, insert, update, delete on table public.pms_snapshot_outcomes to service_role;
