-- ============================================================================
-- TRADING RESEARCH PLATFORM + PM+PD FOUNDATION
-- Migration 002
-- Generated: 2026-08-28
--
-- IMPORTANT
--   * Safe extension migration for an EXISTING Supabase project.
--   * Does NOT alter/drop existing Second1M tables:
--       signals
--       signal_entry_context
--       signal_checkpoints
--       signal_outcomes
--       ticker_direction_stats
--       leaderboard_snapshots
--       leaderboard_history
--       webhook_events
--       import_audit
--       fthc_historical_staging_v1
--       market_daily_history

--       schema_metadata
--   * Adds shared multi-strategy research-management infrastructure.
--   * Adds PM+PD-specific research tables only.
--   * RLS enabled; no public/anon policies are created.
-- ============================================================================

create extension if not exists pgcrypto;

-- ============================================================================
-- COMMON UPDATED_AT FUNCTION
-- ============================================================================

create or replace function public.trp_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ============================================================================
-- 1. SHARED STRATEGY REGISTRY
-- ============================================================================

create table if not exists public.strategies (
  strategy_id uuid primary key default gen_random_uuid(),
  strategy_code text not null unique,
  strategy_name text not null,
  strategy_type text not null default 'strategy'
    check (strategy_type in ('platform','strategy')),
  status text not null default 'active'
    check (status in ('active','paused','research','retired')),
  baseline_model text,
  description text,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_strategies_updated_at on public.strategies;
create trigger trg_strategies_updated_at
before update on public.strategies
for each row execute function public.trp_set_updated_at();

insert into public.strategies
(strategy_code, strategy_name, strategy_type, status, baseline_model, description)
values
('PLATFORM','Trading Research Platform','platform','active',null,
 'Shared infrastructure for market data, research governance, experiments, and cross-strategy tooling.'),
('SECOND1M','Second 1M Candle Monitoring','strategy','active',null,
 'Existing Second 1M research system. Existing signal/research tables remain unchanged.'),
('PMPD','PM + Previous Day Breakout','strategy','research','V4',
 'PMH/PDH bullish and PML/PDL bearish breakout research and forward-validation system.'),
('ORB15','15-Minute ORB','strategy','research',null,
 '15-minute Opening Range Breakout research project.')
on conflict (strategy_code) do update
set
  strategy_name = excluded.strategy_name,
  strategy_type = excluded.strategy_type,
  status = excluded.status,
  baseline_model = coalesce(public.strategies.baseline_model, excluded.baseline_model),
  description = excluded.description,
  updated_at = now();

-- ============================================================================
-- 2. SHARED DATASET VERSIONING
-- ============================================================================

create table if not exists public.datasets (
  dataset_id uuid primary key default gen_random_uuid(),
  strategy_id uuid references public.strategies(strategy_id) on delete restrict,
  dataset_key text not null unique,
  dataset_name text not null,
  dataset_version text not null,
  description text,

  source text not null,
  source_detail text,

  start_date date,
  end_date date,
  universe_name text,
  symbol_count integer check (symbol_count is null or symbol_count >= 0),

  canonical_intraday_tf text not null default '1m',
  timezone text not null default 'America/New_York',

  baseline_model_version text,
  processing_code_version text,

  is_frozen boolean not null default false,
  metadata_json jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  notes text
);

drop trigger if exists trg_datasets_updated_at on public.datasets;
create trigger trg_datasets_updated_at
before update on public.datasets
for each row execute function public.trp_set_updated_at();

create index if not exists idx_datasets_strategy on public.datasets(strategy_id);

-- ============================================================================
-- 3. SHARED RESEARCH RUNS
-- ============================================================================

create table if not exists public.research_runs (
  run_id uuid primary key default gen_random_uuid(),
  strategy_id uuid references public.strategies(strategy_id) on delete restrict,
  dataset_id uuid references public.datasets(dataset_id) on delete cascade,

  run_type text not null check (
    run_type in (
      'historical_ingestion',
      'signal_reconstruction',
      'outcome_calculation',
      'factor_research',
      'forward_validation',
      'parity_validation',
      'maintenance'
    )
  ),
  status text not null default 'ready'
    check (status in ('ready','active','blocked','complete','failed','cancelled')),

  started_at timestamptz,
  completed_at timestamptz,

  symbol_count_requested integer,
  symbol_count_completed integer,
  earliest_bar timestamptz,
  latest_bar timestamptz,

  code_version text,
  model_version text,

  rows_inserted bigint not null default 0,
  rows_updated bigint not null default 0,
  errors_count integer not null default 0,

  parameters_json jsonb not null default '{}'::jsonb,
  notes text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_research_runs_updated_at on public.research_runs;
create trigger trg_research_runs_updated_at
before update on public.research_runs
for each row execute function public.trp_set_updated_at();

create index if not exists idx_research_runs_strategy on public.research_runs(strategy_id);
create index if not exists idx_research_runs_dataset on public.research_runs(dataset_id);
create index if not exists idx_research_runs_status on public.research_runs(status);

-- ============================================================================
-- 4. SHARED PROGRAM PLAN / ROADMAP / TANGENT / DECISION SYSTEM
-- ============================================================================

create table if not exists public.program_phases (
  phase_id uuid primary key default gen_random_uuid(),
  strategy_id uuid not null references public.strategies(strategy_id) on delete cascade,

  phase_code text not null,
  phase_name text not null,
  objective text,

  status text not null default 'backlog'
    check (status in ('backlog','ready','active','blocked','complete','cancelled')),
  sequence_order integer not null,

  entry_criteria text,
  exit_criteria text,

  started_at timestamptz,
  completed_at timestamptz,

  next_phase_code text,
  notes text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique(strategy_id, phase_code)
);

drop trigger if exists trg_program_phases_updated_at on public.program_phases;
create trigger trg_program_phases_updated_at
before update on public.program_phases
for each row execute function public.trp_set_updated_at();

create table if not exists public.research_factors (
  factor_id uuid primary key default gen_random_uuid(),
  strategy_id uuid not null references public.strategies(strategy_id) on delete cascade,

  factor_code text not null,
  family text not null,
  factor_name text not null,
  description text,

  priority integer,
  status text not null default 'not_tested'
    check (status in (
      'not_tested','ready','testing','research_only',
      'validated','rejected','production_candidate'
    )),

  timing_type text not null
    check (timing_type in ('signal_time','post_signal','static','mixed')),
  data_type text,

  data_available boolean,
  implementation_status text,

  tested_n bigint,
  tested_symbols integer,

  finding text,
  predictive_strength text,
  bull_result jsonb,
  bear_result jsonb,
  temporal_robustness text,
  production_status text,

  dependencies text[],
  metadata_json jsonb not null default '{}'::jsonb,
  roadmap_version text not null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique(strategy_id, factor_code)
);

drop trigger if exists trg_research_factors_updated_at on public.research_factors;
create trigger trg_research_factors_updated_at
before update on public.research_factors
for each row execute function public.trp_set_updated_at();

create index if not exists idx_research_factors_strategy_family
  on public.research_factors(strategy_id, family);
create index if not exists idx_research_factors_strategy_status
  on public.research_factors(strategy_id, status);

create table if not exists public.research_experiments (
  experiment_id uuid primary key default gen_random_uuid(),
  strategy_id uuid not null references public.strategies(strategy_id) on delete cascade,
  factor_id uuid references public.research_factors(factor_id) on delete set null,
  dataset_id uuid references public.datasets(dataset_id) on delete set null,

  experiment_code text not null,
  experiment_name text not null,
  hypothesis text,

  status text not null default 'ready'
    check (status in ('ready','active','blocked','complete','rejected','cancelled')),

  universe text,
  start_date date,
  end_date date,

  n bigint,
  symbol_count integer,

  primary_metric text,
  baseline_value numeric,
  result_value numeric,
  lift_value numeric,

  bull_result jsonb,
  bear_result jsonb,
  confidence_level text,

  finding text,
  decision text,

  sql_or_notebook_reference text,
  code_version text,
  model_version text,

  parameters_json jsonb not null default '{}'::jsonb,
  result_json jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  completed_at timestamptz,

  unique(strategy_id, experiment_code)
);

create index if not exists idx_research_experiments_strategy
  on public.research_experiments(strategy_id);
create index if not exists idx_research_experiments_factor
  on public.research_experiments(factor_id);

create table if not exists public.project_backlog (
  backlog_id uuid primary key default gen_random_uuid(),
  strategy_id uuid not null references public.strategies(strategy_id) on delete cascade,

  title text not null,
  description text,
  category text,
  priority integer,

  status text not null default 'backlog'
    check (status in ('backlog','ready','active','blocked','complete','rejected','cancelled')),

  origin_phase text,
  blocking_current_phase boolean not null default false,
  why_it_matters text,
  promoted_to_phase text,

  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_project_backlog_updated_at on public.project_backlog;
create trigger trg_project_backlog_updated_at
before update on public.project_backlog
for each row execute function public.trp_set_updated_at();

create table if not exists public.project_decisions (
  decision_id uuid primary key default gen_random_uuid(),
  strategy_id uuid not null references public.strategies(strategy_id) on delete cascade,

  decision_date timestamptz not null default now(),
  title text not null,
  decision text not null,
  rationale text,
  evidence text,

  affects_model_version text,
  supersedes_decision_id uuid references public.project_decisions(decision_id) on delete set null,

  status text not null default 'active'
    check (status in ('active','superseded','reversed')),

  metadata_json jsonb not null default '{}'::jsonb
);

create index if not exists idx_project_decisions_strategy_date
  on public.project_decisions(strategy_id, decision_date desc);

create table if not exists public.project_state (
  strategy_id uuid primary key references public.strategies(strategy_id) on delete cascade,

  active_phase_code text,
  active_phase_name text,
  next_phase_code text,
  next_phase_name text,

  blocker_count integer not null default 0,

  baseline_model text,
  baseline_status text,
  forward_validation_status text,
  historical_dataset_status text,

  active_tangent_count integer not null default 0,
  last_decision text,
  roadmap_version text,

  metadata_json jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_project_state_updated_at on public.project_state;
create trigger trg_project_state_updated_at
before update on public.project_state
for each row execute function public.trp_set_updated_at();

-- ============================================================================
-- 5. PM+PD CORE RESEARCH TABLES
-- ============================================================================

create table if not exists public.pm_pd_candidates (
  candidate_id uuid primary key default gen_random_uuid(),
  dataset_id uuid not null references public.datasets(dataset_id) on delete cascade,
  run_id uuid references public.research_runs(run_id) on delete set null,

  symbol text not null,
  trade_date date not null,
  candidate_timestamp timestamptz not null,
  direction text not null check (direction in ('bull','bear')),

  candidate_stage text not null check (
    candidate_stage in (
      'level_interaction',
      'dual_level_candidate',
      'raw_breakout',
      'confirmation_candidate',
      'v4_signal'
    )
  ),

  pmh numeric,
  pml numeric,
  pdh numeric,
  pdl numeric,

  bull_final_level numeric,
  bear_final_level numeric,
  final_level_name text,

  first_level_crossed text,
  first_level_cross_timestamp timestamptz,
  second_level_cross_timestamp timestamptz,

  raw_breakout boolean not null default false,
  confirmation_available boolean not null default false,
  v4_valid boolean not null default false,

  source_event_key text,
  metadata_json jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique(dataset_id, symbol, candidate_timestamp, direction, candidate_stage)
);

drop trigger if exists trg_pm_pd_candidates_updated_at on public.pm_pd_candidates;
create trigger trg_pm_pd_candidates_updated_at
before update on public.pm_pd_candidates
for each row execute function public.trp_set_updated_at();

create index if not exists idx_pm_pd_candidates_dataset_symbol_time
  on public.pm_pd_candidates(dataset_id, symbol, candidate_timestamp);

create table if not exists public.pm_pd_signals (
  signal_id uuid primary key default gen_random_uuid(),
  candidate_id uuid references public.pm_pd_candidates(candidate_id) on delete set null,
  dataset_id uuid not null references public.datasets(dataset_id) on delete cascade,
  run_id uuid references public.research_runs(run_id) on delete set null,

  signal_key text not null,
  symbol text not null,
  direction text not null check (direction in ('bull','bear')),
  signal_timestamp timestamptz not null,
  trade_date date not null,

  confirmation_tf text not null default '5m',
  reference_price numeric not null,

  final_breakout_level numeric,
  final_breakout_name text,

  research_event boolean not null default true,
  production_signal boolean not null default false,

  v4_score numeric,
  exact_grade text,
  grade_family text check (grade_family is null or grade_family in ('A','B','C','Weak')),
  v4_profile text,

  priority text check (
    priority is null or priority in ('PRIME','CONDITIONAL','RESEARCH','LOW','OBSERVE')
  ),
  trade_type text check (
    trade_type is null or trade_type in ('EXPANSION','SCALP','OBSERVE')
  ),

  tqs numeric,
  confidence text,

  data_source text not null,
  research_population text,
  historical_set text,

  schema_version text not null,
  collector_build text,
  model_version text not null,

  raw_payload jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique(signal_key),
  unique(dataset_id, symbol, signal_timestamp, direction, model_version)
);

drop trigger if exists trg_pm_pd_signals_updated_at on public.pm_pd_signals;
create trigger trg_pm_pd_signals_updated_at
before update on public.pm_pd_signals
for each row execute function public.trp_set_updated_at();

create index if not exists idx_pm_pd_signals_symbol_time
  on public.pm_pd_signals(symbol, signal_timestamp);
create index if not exists idx_pm_pd_signals_grade_profile
  on public.pm_pd_signals(grade_family, v4_profile);
create index if not exists idx_pm_pd_signals_priority
  on public.pm_pd_signals(priority);

create table if not exists public.pm_pd_entry_context (
  signal_id uuid primary key references public.pm_pd_signals(signal_id) on delete cascade,

  -- Breakout levels / structure
  pmh numeric,
  pml numeric,
  pdh numeric,
  pdl numeric,
  final_breakout_level numeric,
  final_breakout_name text,

  penetration_atr_pct numeric,
  body_range_pct numeric,
  close_position_pct numeric,
  range_atr_pct numeric,
  confirmation_speed_bars integer,

  distance_between_required_levels numeric,
  distance_between_levels_atr numeric,
  first_level_crossed text,
  time_between_level_crosses_sec integer,

  pre_breakout_extension_pct numeric,
  pre_breakout_extension_atr numeric,

  -- Confirmation candle
  conf_open numeric,
  conf_high numeric,
  conf_low numeric,
  conf_close numeric,
  conf_volume numeric,
  atr_value numeric,

  -- Premarket
  premarket_open numeric,
  premarket_high numeric,
  premarket_low numeric,
  premarket_close numeric,
  premarket_volume numeric,
  premarket_range_pct numeric,
  premarket_range_atr numeric,
  premarket_return_pct numeric,

  -- VWAP / volume
  rth_vwap numeric,
  distance_from_vwap_pct numeric,
  distance_from_vwap_atr numeric,
  vwap_slope numeric,
  correct_vwap_side boolean,

  relative_volume numeric,
  volume_expansion_ratio numeric,

  -- Higher-timeframe stock context
  previous_rth_close numeric,
  prev_day_open numeric,
  prev_day_high numeric,
  prev_day_low numeric,
  prev_day_close numeric,
  prev_day_return_pct numeric,
  prev_day_body_pct numeric,
  prev_day_range_pct numeric,
  prev_day_range_atr numeric,
  prev_day_close_location numeric,

  return_3d numeric,
  return_5d numeric,
  return_10d numeric,
  return_20d numeric,

  weekly_return_pct numeric,
  weekly_range_position numeric,
  weekly_bias text,
  weekly_bias_version text,

  gap_pct numeric,
  gap_direction text,
  volatility_regime text,

  -- Market context
  spy_prev_day_return numeric,
  qqq_prev_day_return numeric,
  dia_prev_day_return numeric,
  spy_current_return numeric,
  qqq_current_return numeric,
  dia_current_return numeric,
  market_bias text,
  market_bias_version text,
  signal_market_alignment text,

  sector_symbol text,
  sector_current_return numeric,
  sector_alignment text,

  extra_features jsonb not null default '{}'::jsonb,
  raw_payload jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_pm_pd_entry_context_updated_at on public.pm_pd_entry_context;
create trigger trg_pm_pd_entry_context_updated_at
before update on public.pm_pd_entry_context
for each row execute function public.trp_set_updated_at();

create table if not exists public.pm_pd_checkpoints (
  id uuid primary key default gen_random_uuid(),
  signal_id uuid not null references public.pm_pd_signals(signal_id) on delete cascade,

  checkpoint_minute smallint not null,
  checkpoint_timestamp timestamptz,
  has_checkpoint boolean not null default true,

  open numeric,
  high numeric,
  low numeric,
  close numeric,
  rth_vwap numeric,

  mfe_pct numeric,
  mae_pct numeric,
  path_score numeric,

  close_vs_reference_pct numeric,
  close_vs_vwap_pct numeric,

  vwap_state text,
  vwap_lost_since_signal boolean,
  vwap_reclaimed boolean,

  pm_level_state text,
  pd_level_state text,
  final_level_state text,

  pm_lost boolean,
  pm_reclaimed boolean,
  pd_lost boolean,
  pd_reclaimed boolean,
  final_level_lost boolean,
  final_level_reclaimed boolean,

  health_state_code smallint,
  health_state text,
  weak_checkpoint_count smallint,

  had_w1 boolean,
  had_w2 boolean,
  had_w3 boolean,
  recovery_state boolean,
  warning_model_version text,

  raw_payload jsonb,
  created_at timestamptz not null default now(),

  unique(signal_id, checkpoint_minute)
);

create index if not exists idx_pm_pd_checkpoints_signal
  on public.pm_pd_checkpoints(signal_id, checkpoint_minute);

create table if not exists public.pm_pd_outcomes (
  signal_id uuid primary key references public.pm_pd_signals(signal_id) on delete cascade,

  primary_outcome_code smallint,
  primary_outcome text,
  outcome_100v050_code smallint,

  outcome_timestamp timestamptz,

  fav_010_timestamp timestamptz,
  fav_025_timestamp timestamptz,
  fav_050_timestamp timestamptz,
  fav_075_timestamp timestamptz,
  fav_100_timestamp timestamptz,

  adv_010_timestamp timestamptz,
  adv_025_timestamp timestamptz,
  adv_035_timestamp timestamptz,
  adv_050_timestamp timestamptz,
  adv_075_timestamp timestamptz,
  adv_100_timestamp timestamptz,

  minutes_to_010 numeric,
  minutes_to_025 numeric,
  minutes_to_050 numeric,
  minutes_to_075 numeric,
  minutes_to_100 numeric,

  minutes_to_adverse_010 numeric,
  minutes_to_adverse_025 numeric,
  minutes_to_adverse_035 numeric,
  minutes_to_adverse_050 numeric,
  minutes_to_adverse_075 numeric,
  minutes_to_adverse_100 numeric,

  final_mfe_pct numeric,
  final_mfe_timestamp timestamptz,
  final_mae_pct numeric,
  final_mae_timestamp timestamptz,

  highest_warning_reached smallint,
  recovery_before_resolution boolean,

  session_complete boolean not null default false,
  resolved_at timestamptz,
  raw_payload jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_pm_pd_outcomes_updated_at on public.pm_pd_outcomes;
create trigger trg_pm_pd_outcomes_updated_at
before update on public.pm_pd_outcomes
for each row execute function public.trp_set_updated_at();

create table if not exists public.pm_pd_post_signal_events (
  event_id uuid primary key default gen_random_uuid(),
  signal_id uuid not null references public.pm_pd_signals(signal_id) on delete cascade,

  event_timestamp timestamptz not null,
  minutes_since_signal numeric,
  bars_since_signal integer,

  event_type text not null,
  event_level text,
  event_value numeric,

  price numeric,
  mfe_at_event numeric,
  mae_at_event numeric,

  model_version text,
  metadata_json jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),

  unique(signal_id, event_type, event_timestamp, model_version)
);

create index if not exists idx_pm_pd_post_signal_events_signal_time
  on public.pm_pd_post_signal_events(signal_id, event_timestamp);
create index if not exists idx_pm_pd_post_signal_events_type
  on public.pm_pd_post_signal_events(event_type);

-- ============================================================================
-- 6. SEED PM+PD PROGRAM PLAN
-- ============================================================================

with pmpd as (
  select strategy_id from public.strategies where strategy_code = 'PMPD'
)
insert into public.program_phases
(strategy_id, phase_code, phase_name, objective, status, sequence_order, exit_criteria, next_phase_code)
select strategy_id, phase_code, phase_name, objective, status, sequence_order, exit_criteria, next_phase_code
from pmpd
cross join (
  values
  ('8H-1','Master Research Roadmap',
   'Create authoritative PM+PD research roadmap and governance rules.',
   'complete',1,
   'Roadmap approved and assigned to shared research-management system.',
   '8H-2'),

  ('8H-2','Research Factor & Data Dictionary',
   'Map planned research to signal-time/post-signal, raw/derived, source, resolution, and storage.',
   'complete',2,
   'Research/data dictionary approved.',
   '8H-3'),

  ('8H-3','Shared Supabase Architecture',
   'Audit existing Second1M schema and implement shared platform + PM+PD foundation.',
   'active',3,
   'Migration 002 applied successfully and PM+PD/shared tables verified.',
   '8H-4'),

  ('8H-4','Historical Data Architecture',
   'Define Massive + TradingView + canonical raw-market-data architecture.',
   'ready',4,
   'Historical acquisition, caching, normalization, and reproducibility architecture approved.',
   '8H-5'),

  ('8H-5','Frozen V4 Parity Specification',
   'Document the exact frozen V4 logic external reconstruction must reproduce.',
   'backlog',5,
   'Parity specification complete with test fixtures.',
   '8H-6'),

  ('8H-6','Historical Engine & Ingestion',
   'Build PM+PD historical reconstruction and Supabase ingestion pipeline.',
   'backlog',6,
   'Pipeline reconstructs candidates/signals/outcomes and writes clean versioned rows.',
   '8H-7'),

  ('8H-7','Small-Sample Parity Validation',
   'Compare external PM+PD reconstruction with TradingView.',
   'backlog',7,
   'Counts, timestamps, classifications, and outcomes reconcile within approved tolerance.',
   '8H-8'),

  ('8H-8','112-Stock Historical Bootstrap',
   'Load four sets of 28 stocks into a versioned PM+PD historical dataset.',
   'backlog',8,
   '112-stock bootstrap complete with coverage/data-quality audit.',
   '8H-9'),

  ('8H-9','Expanded-Universe V4 Baseline Replication',
   'Re-test frozen V4 findings on larger historical universe before optimization.',
   'backlog',9,
   'Expanded V4 baseline metrics complete and compared with original 16-stock study.',
   '8H-10'),

  ('8H-10','Individual-Factor Research',
   'Test signal-time factors individually before interaction mining.',
   'backlog',10,
   'Priority factors tested with N, breadth, robustness, and null findings recorded.',
   '8H-11'),

  ('8H-11','Trade Health / Warning Research',
   'Develop evidence-based W1/W2/W3 deterioration candidates.',
   'backlog',11,
   'Warning candidates evaluated for deterioration lift and recovery rate.',
   '8H-12'),

  ('8H-12','Controlled Interaction Research',
   'Test interactions only among individually supported factors.',
   'backlog',12,
   'Interaction candidates evaluated without uncontrolled data mining.',
   '8H-13'),

  ('8H-13','Candidate V5 Model',
   'Create frozen V5 candidate from validated improvements only.',
   'backlog',13,
   'Candidate model specified and frozen.',
   '8H-14'),

  ('8H-14','Holdout / Out-of-Sample Validation',
   'Validate V5 candidate against untouched data and frozen V4 baseline.',
   'backlog',14,
   'Holdout comparison complete.',
   '8H-15'),

  ('8H-15','Production Decision',
   'Choose V5, retain V4, or continue research based on validation.',
   'backlog',15,
   'Production decision recorded.',
   null)
) as v(phase_code,phase_name,objective,status,sequence_order,exit_criteria,next_phase_code)
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
-- 7. SEED PM+PD DECISIONS
-- ============================================================================

with pmpd as (
  select strategy_id from public.strategies where strategy_code = 'PMPD'
)
insert into public.project_decisions
(strategy_id, title, decision, rationale, evidence, affects_model_version)
select
  pmpd.strategy_id,
  v.title,
  v.decision,
  v.rationale,
  v.evidence,
  v.affects_model_version
from pmpd
cross join (
  values
  ('Primary benchmark',
   '+0.50% favorable before -0.50% adverse remains the primary PM+PD benchmark.',
   'Maintains symmetric comparison and direct comparability across scenarios.',
   'Established throughout PM+PD historical research.',
   'V4'),

  ('Frozen V4 baseline',
   'V4 remains the baseline model and must not be silently overwritten by later candidate models.',
   'Every proposed improvement must be measured against a stable reference.',
   '16-stock historical research plus active forward-validation framework.',
   'V4'),

  ('Confirmation timeframe',
   '5-minute confirmation remains the frozen V4 baseline.',
   'Historical work favored 5-minute confirmation for filtering/quality despite entry latency.',
   'Existing V4 research and forward-validation build.',
   'V4'),

  ('Shared Supabase source of truth',
   'Supabase is authoritative for PM+PD roadmap, program status, experiments, tangents, decisions, and derived research data.',
   'Prevents roadmap drift and preserves experiment provenance.',
   'Approved during 8H architecture work.',
   null),

  ('Protect existing Second1M tables',
   'Existing Second1M production/research tables remain unchanged during PM+PD setup.',
   'Avoids risking a working pipeline while allowing shared governance infrastructure alongside it.',
   'Existing database audit completed during 8H-3B.',
   null),

  ('Shared management infrastructure',
   'Roadmap/status/plan/tangent/decision infrastructure is multi-strategy and reusable by PM+PD, Second1M, ORB, and PLATFORM work.',
   'Prevents duplicating project-management systems and supports later Second1M roadmap migration.',
   'Architecture decision during 8H-3B/3C.',
   null),

  ('Separate Signal Quality and Trade Health',
   'Entry-known Signal Quality and post-entry Trade Health/Warning features remain separate domains.',
   'Prevents future information leakage and preserves clean interpretation.',
   'Master roadmap architecture.',
   null),

  ('Raw data retention',
   'Retain reproducible access to canonical 1-minute raw market data outside Supabase initially.',
   'Allows future threshold changes and multi-timeframe reconstruction without bloating Migration 002.',
   'Research/Data Dictionary decision.',
   null)
) as v(title,decision,rationale,evidence,affects_model_version);

-- ============================================================================
-- 8. SEED PM+PD CURRENT STATE
-- ============================================================================

with pmpd as (
  select strategy_id from public.strategies where strategy_code = 'PMPD'
)
insert into public.project_state
(
  strategy_id,
  active_phase_code,
  active_phase_name,
  next_phase_code,
  next_phase_name,
  blocker_count,
  baseline_model,
  baseline_status,
  forward_validation_status,
  historical_dataset_status,
  active_tangent_count,
  last_decision,
  roadmap_version,
  metadata_json
)
select
  strategy_id,
  '8H-3',
  'Shared Supabase Architecture',
  '8H-4',
  'Historical Data Architecture',
  0,
  'V4',
  'FROZEN_BASELINE',
  'IN_PROGRESS',
  'NOT_BUILT',
  0,
  'Existing Second1M tables protected; shared platform + PM+PD foundation is the approved architecture.',
  'PMPD-RM-1.0',
  jsonb_build_object(
    'historical_target_universe',112,
    'stock_sets',4,
    'stocks_per_set',28,
    'primary_benchmark','+0.50% before -0.50%',
    'baseline_confirmation_tf','5m'
  )
from pmpd
on conflict (strategy_id) do update
set
  active_phase_code = excluded.active_phase_code,
  active_phase_name = excluded.active_phase_name,
  next_phase_code = excluded.next_phase_code,
  next_phase_name = excluded.next_phase_name,
  blocker_count = excluded.blocker_count,
  baseline_model = excluded.baseline_model,
  baseline_status = excluded.baseline_status,
  forward_validation_status = excluded.forward_validation_status,
  historical_dataset_status = excluded.historical_dataset_status,
  active_tangent_count = excluded.active_tangent_count,
  last_decision = excluded.last_decision,
  roadmap_version = excluded.roadmap_version,
  metadata_json = excluded.metadata_json,
  updated_at = now();

-- ============================================================================
-- 9. REGISTER SECOND1M CURRENT STATE PLACEHOLDER
--    No roadmap reconstruction is attempted in this migration.
-- ============================================================================

with s1m as (
  select strategy_id from public.strategies where strategy_code = 'SECOND1M'
)
insert into public.project_state
(
  strategy_id,
  baseline_status,
  historical_dataset_status,
  last_decision,
  metadata_json
)
select
  strategy_id,
  'EXISTING_SYSTEM_PROTECTED',
  'EXISTING',
  'Second1M registered in shared project-management framework; roadmap/status migration deferred.',
  jsonb_build_object('roadmap_migration_status','DEFERRED')
from s1m
on conflict (strategy_id) do nothing;

-- ============================================================================
-- 10. SHARED PROJECT DASHBOARD VIEW
-- ============================================================================

create or replace view public.v_trading_research_dashboard as
select
  s.strategy_code,
  s.strategy_name,
  s.strategy_type,
  s.status as strategy_status,
  ps.active_phase_code,
  ps.active_phase_name,
  ps.next_phase_code,
  ps.next_phase_name,
  ps.blocker_count,
  ps.baseline_model,
  ps.baseline_status,
  ps.forward_validation_status,
  ps.historical_dataset_status,
  ps.active_tangent_count,
  ps.last_decision,
  ps.roadmap_version,
  ps.updated_at,
  (
    select count(*)
    from public.research_factors rf
    where rf.strategy_id = s.strategy_id
  ) as total_research_factors,
  (
    select count(*)
    from public.project_backlog pb
    where pb.strategy_id = s.strategy_id
      and pb.status not in ('complete','rejected','cancelled')
  ) as open_backlog_items
from public.strategies s
left join public.project_state ps on ps.strategy_id = s.strategy_id
order by
  case when s.strategy_code = 'PLATFORM' then 0 else 1 end,
  s.strategy_name;

-- ============================================================================
-- 11. RLS
-- ============================================================================

alter table public.strategies enable row level security;
alter table public.datasets enable row level security;
alter table public.research_runs enable row level security;
alter table public.program_phases enable row level security;
alter table public.research_factors enable row level security;
alter table public.research_experiments enable row level security;
alter table public.project_backlog enable row level security;
alter table public.project_decisions enable row level security;
alter table public.project_state enable row level security;

alter table public.pm_pd_candidates enable row level security;
alter table public.pm_pd_signals enable row level security;
alter table public.pm_pd_entry_context enable row level security;
alter table public.pm_pd_checkpoints enable row level security;
alter table public.pm_pd_outcomes enable row level security;
alter table public.pm_pd_post_signal_events enable row level security;

-- No anon/public policies created.
-- Service-role ingestion remains server-side only.

-- ============================================================================
-- END MIGRATION 002
-- ============================================================================
