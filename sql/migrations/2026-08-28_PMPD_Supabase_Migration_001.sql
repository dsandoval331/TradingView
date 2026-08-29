-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Supabase Migration 001
-- Generated: 2026-08-28
--
-- PURPOSE
--   1) Research data model
--   2) Project-management / roadmap model
--   3) Versioned datasets + experiments
--   4) Frozen V4 baseline preservation
--
-- IMPORTANT
--   - Signal-time data and post-signal data are intentionally separated.
--   - Historical model outputs are versioned and should never be overwritten
--     simply because a later V5/V6 model changes classification logic.
--   - Raw 1-minute Massive bars are NOT stored here in Migration 001.
--     Cache canonical market data outside Supabase initially and store the
--     reproducible source/version metadata in datasets + research_runs.
-- ============================================================================

create extension if not exists pgcrypto;

-- ============================================================================
-- COMMON UPDATED_AT TRIGGER
-- ============================================================================

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ============================================================================
-- 1. DATASET / RUN VERSIONING
-- ============================================================================

create table if not exists public.datasets (
  dataset_id uuid primary key default gen_random_uuid(),
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
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  notes text
);

create trigger trg_datasets_updated_at
before update on public.datasets
for each row execute function public.set_updated_at();

create table if not exists public.research_runs (
  run_id uuid primary key default gen_random_uuid(),
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
  status text not null default 'ready' check (
    status in ('ready','active','blocked','complete','failed','cancelled')
  ),

  started_at timestamptz,
  completed_at timestamptz,

  symbol_count_requested integer check (symbol_count_requested is null or symbol_count_requested >= 0),
  symbol_count_completed integer check (symbol_count_completed is null or symbol_count_completed >= 0),

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

create trigger trg_research_runs_updated_at
before update on public.research_runs
for each row execute function public.set_updated_at();

create index if not exists idx_research_runs_dataset on public.research_runs(dataset_id);
create index if not exists idx_research_runs_status on public.research_runs(status);
create index if not exists idx_research_runs_type on public.research_runs(run_type);

-- ============================================================================
-- 2. SYMBOL MASTER
-- ============================================================================

create table if not exists public.symbols (
  symbol_id uuid primary key default gen_random_uuid(),
  ticker text not null,
  exchange text,
  asset_type text not null default 'equity',
  sector text,
  industry text,

  active boolean not null default true,
  first_seen date,
  last_seen date,

  massive_ticker text,
  tradingview_ticker text,

  metadata_json jsonb not null default '{}'::jsonb,
  notes text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (ticker, exchange)
);

create trigger trg_symbols_updated_at
before update on public.symbols
for each row execute function public.set_updated_at();

create index if not exists idx_symbols_ticker on public.symbols(ticker);
create index if not exists idx_symbols_sector on public.symbols(sector);

-- ============================================================================
-- 3. PM+PD CANDIDATE POPULATION
-- ============================================================================

create table if not exists public.pm_pd_candidates (
  candidate_id uuid primary key default gen_random_uuid(),
  dataset_id uuid not null references public.datasets(dataset_id) on delete cascade,
  run_id uuid references public.research_runs(run_id) on delete set null,
  symbol_id uuid not null references public.symbols(symbol_id) on delete restrict,

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

  unique (dataset_id, symbol_id, candidate_timestamp, direction, candidate_stage)
);

create trigger trg_pm_pd_candidates_updated_at
before update on public.pm_pd_candidates
for each row execute function public.set_updated_at();

create index if not exists idx_candidates_dataset_symbol_time
  on public.pm_pd_candidates(dataset_id, symbol_id, candidate_timestamp);

create index if not exists idx_candidates_stage
  on public.pm_pd_candidates(candidate_stage);

create index if not exists idx_candidates_trade_date
  on public.pm_pd_candidates(trade_date);

-- ============================================================================
-- 4. CONFIRMED PM+PD SIGNALS
-- ============================================================================

create table if not exists public.pm_pd_signals (
  signal_id uuid primary key default gen_random_uuid(),
  candidate_id uuid references public.pm_pd_candidates(candidate_id) on delete set null,
  dataset_id uuid not null references public.datasets(dataset_id) on delete cascade,
  run_id uuid references public.research_runs(run_id) on delete set null,
  symbol_id uuid not null references public.symbols(symbol_id) on delete restrict,

  signal_timestamp timestamptz not null,
  trade_date date not null,
  direction text not null check (direction in ('bull','bear')),

  confirmation_tf text not null default '5m',
  reference_price numeric not null,

  final_breakout_level numeric,
  final_breakout_name text,

  v4_score numeric,
  exact_grade text,
  grade_family text check (grade_family is null or grade_family in ('A','B','C','Weak')),
  v4_profile text,
  priority text check (priority is null or priority in ('PRIME','CONDITIONAL','RESEARCH','LOW','OBSERVE')),
  trade_type text check (trade_type is null or trade_type in ('EXPANSION','SCALP','OBSERVE')),

  tqs numeric,
  confidence text,

  model_version text not null,
  source_event_key text,
  metadata_json jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (dataset_id, symbol_id, signal_timestamp, direction, model_version)
);

create trigger trg_pm_pd_signals_updated_at
before update on public.pm_pd_signals
for each row execute function public.set_updated_at();

create index if not exists idx_signals_dataset_symbol_time
  on public.pm_pd_signals(dataset_id, symbol_id, signal_timestamp);

create index if not exists idx_signals_trade_date
  on public.pm_pd_signals(trade_date);

create index if not exists idx_signals_direction
  on public.pm_pd_signals(direction);

create index if not exists idx_signals_grade_profile
  on public.pm_pd_signals(grade_family, v4_profile);

create index if not exists idx_signals_priority
  on public.pm_pd_signals(priority);

-- ============================================================================
-- 5. SIGNAL-TIME FEATURES
-- ============================================================================

create table if not exists public.pm_pd_signal_features (
  signal_id uuid primary key references public.pm_pd_signals(signal_id) on delete cascade,

  -- Breakout / confirmation structure
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

  -- Confirmation candle raw values
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
  premarket_range_pct numeric,
  premarket_range_atr numeric,
  premarket_return_pct numeric,

  -- VWAP / volume
  vwap numeric,
  distance_from_vwap_pct numeric,
  distance_from_vwap_atr numeric,
  vwap_slope numeric,
  correct_vwap_side boolean,

  relative_volume numeric,
  volume_expansion_ratio numeric,

  -- Flexible future signal-time research values
  extra_features jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger trg_pm_pd_signal_features_updated_at
before update on public.pm_pd_signal_features
for each row execute function public.set_updated_at();

-- ============================================================================
-- 6. SYMBOL / HIGHER-TIMEFRAME CONTEXT
-- ============================================================================

create table if not exists public.symbol_context (
  signal_id uuid primary key references public.pm_pd_signals(signal_id) on delete cascade,

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

  trend_3d_slope numeric,
  trend_5d_slope numeric,
  trend_10d_slope numeric,
  trend_20d_slope numeric,

  hh_hl_structure text,

  weekly_open numeric,
  weekly_high numeric,
  weekly_low numeric,
  weekly_close numeric,
  weekly_return_pct numeric,
  weekly_range_position numeric,

  weekly_bias_version text,
  weekly_bias text check (weekly_bias is null or weekly_bias in ('bullish','neutral','bearish')),

  gap_pct numeric,
  gap_direction text check (gap_direction is null or gap_direction in ('up','flat','down')),

  volatility_regime text,
  extra_context jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger trg_symbol_context_updated_at
before update on public.symbol_context
for each row execute function public.set_updated_at();

-- ============================================================================
-- 7. MARKET CONTEXT
-- ============================================================================

create table if not exists public.market_context (
  signal_id uuid primary key references public.pm_pd_signals(signal_id) on delete cascade,

  spy_prev_day_return numeric,
  qqq_prev_day_return numeric,
  dia_prev_day_return numeric,

  spy_current_return numeric,
  qqq_current_return numeric,
  dia_current_return numeric,

  spy_3d_return numeric,
  qqq_3d_return numeric,
  dia_3d_return numeric,

  spy_5d_return numeric,
  qqq_5d_return numeric,
  dia_5d_return numeric,

  spy_10d_return numeric,
  qqq_10d_return numeric,
  dia_10d_return numeric,

  spy_20d_return numeric,
  qqq_20d_return numeric,
  dia_20d_return numeric,

  spy_velocity numeric,
  qqq_velocity numeric,
  dia_velocity numeric,

  market_regime_version text,
  market_bias text check (market_bias is null or market_bias in ('bullish','mixed','bearish')),
  signal_market_alignment text check (
    signal_market_alignment is null or
    signal_market_alignment in ('aligned','mixed','opposed')
  ),

  sector_symbol text,
  sector_current_return numeric,
  sector_alignment text,

  extra_market_context jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger trg_market_context_updated_at
before update on public.market_context
for each row execute function public.set_updated_at();

-- ============================================================================
-- 8. POST-SIGNAL OUTCOMES
-- ============================================================================

create table if not exists public.pm_pd_outcomes (
  signal_id uuid primary key references public.pm_pd_signals(signal_id) on delete cascade,

  outcome_complete boolean not null default false,
  resolution_timestamp timestamptz,

  fav_010_hit boolean,
  fav_010_timestamp timestamptz,
  fav_025_hit boolean,
  fav_025_timestamp timestamptz,
  fav_050_hit boolean,
  fav_050_timestamp timestamptz,
  fav_075_hit boolean,
  fav_075_timestamp timestamptz,
  fav_100_hit boolean,
  fav_100_timestamp timestamptz,

  adv_010_hit boolean,
  adv_010_timestamp timestamptz,
  adv_025_hit boolean,
  adv_025_timestamp timestamptz,
  adv_035_hit boolean,
  adv_035_timestamp timestamptz,
  adv_050_hit boolean,
  adv_050_timestamp timestamptz,
  adv_075_hit boolean,
  adv_075_timestamp timestamptz,
  adv_100_hit boolean,
  adv_100_timestamp timestamptz,

  fav050_before_adv050 boolean,
  first_outcome text check (
    first_outcome is null or
    first_outcome in ('favorable','adverse','both_same_bar','neither')
  ),

  mfe_pct numeric,
  mfe_timestamp timestamptz,
  mae_pct numeric,
  mae_timestamp timestamptz,

  minutes_to_fav010 numeric,
  minutes_to_fav025 numeric,
  minutes_to_fav050 numeric,
  minutes_to_fav075 numeric,
  minutes_to_fav100 numeric,

  minutes_to_adv010 numeric,
  minutes_to_adv025 numeric,
  minutes_to_adv035 numeric,
  minutes_to_adv050 numeric,
  minutes_to_adv075 numeric,
  minutes_to_adv100 numeric,

  same_bar_both boolean,
  extra_outcome jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger trg_pm_pd_outcomes_updated_at
before update on public.pm_pd_outcomes
for each row execute function public.set_updated_at();

create index if not exists idx_outcomes_ff050
  on public.pm_pd_outcomes(fav050_before_adv050);

create index if not exists idx_outcomes_complete
  on public.pm_pd_outcomes(outcome_complete);

-- ============================================================================
-- 9. POST-SIGNAL EVENTS / WARNING RESEARCH
-- ============================================================================

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

  unique (signal_id, event_type, event_timestamp, model_version)
);

create index if not exists idx_post_events_signal_time
  on public.pm_pd_post_signal_events(signal_id, event_timestamp);

create index if not exists idx_post_events_type
  on public.pm_pd_post_signal_events(event_type);

-- ============================================================================
-- 10. PROGRAM PLAN
-- ============================================================================

create table if not exists public.program_phases (
  phase_id uuid primary key default gen_random_uuid(),
  project_key text not null default 'PMPD',
  phase_code text not null,
  phase_name text not null,

  objective text,
  status text not null default 'backlog' check (
    status in ('backlog','ready','active','blocked','complete','cancelled')
  ),
  sequence_order integer not null,

  entry_criteria text,
  exit_criteria text,

  started_at timestamptz,
  completed_at timestamptz,

  next_phase_code text,
  notes text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (project_key, phase_code)
);

create trigger trg_program_phases_updated_at
before update on public.program_phases
for each row execute function public.set_updated_at();

create index if not exists idx_program_phases_project_status
  on public.program_phases(project_key, status);

-- ============================================================================
-- 11. MASTER RESEARCH FACTOR ROADMAP
-- ============================================================================

create table if not exists public.research_factors (
  factor_id uuid primary key default gen_random_uuid(),
  project_key text not null default 'PMPD',

  factor_code text not null,
  family text not null,
  factor_name text not null,
  description text,

  priority integer,
  status text not null default 'not_tested' check (
    status in (
      'not_tested',
      'ready',
      'testing',
      'research_only',
      'validated',
      'rejected',
      'production_candidate'
    )
  ),

  timing_type text not null check (
    timing_type in ('signal_time','post_signal','static','mixed')
  ),
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

  roadmap_version text not null default 'PMPD-RM-1.0',

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (project_key, factor_code)
);

create trigger trg_research_factors_updated_at
before update on public.research_factors
for each row execute function public.set_updated_at();

create index if not exists idx_research_factors_family
  on public.research_factors(project_key, family);

create index if not exists idx_research_factors_status
  on public.research_factors(project_key, status);

create index if not exists idx_research_factors_priority
  on public.research_factors(project_key, priority);

-- ============================================================================
-- 12. RESEARCH EXPERIMENTS
-- ============================================================================

create table if not exists public.research_experiments (
  experiment_id uuid primary key default gen_random_uuid(),
  project_key text not null default 'PMPD',

  factor_id uuid references public.research_factors(factor_id) on delete set null,
  dataset_id uuid references public.datasets(dataset_id) on delete set null,

  experiment_code text not null,
  experiment_name text not null,
  hypothesis text,

  status text not null default 'ready' check (
    status in ('ready','active','blocked','complete','rejected','cancelled')
  ),

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

  unique (project_key, experiment_code)
);

create index if not exists idx_experiments_factor on public.research_experiments(factor_id);
create index if not exists idx_experiments_dataset on public.research_experiments(dataset_id);
create index if not exists idx_experiments_status on public.research_experiments(status);

-- ============================================================================
-- 13. TANGENT / BACKLOG MANAGEMENT
-- ============================================================================

create table if not exists public.project_backlog (
  backlog_id uuid primary key default gen_random_uuid(),
  project_key text not null default 'PMPD',

  title text not null,
  description text,

  category text,
  priority integer,
  status text not null default 'backlog' check (
    status in ('backlog','ready','active','blocked','complete','rejected','cancelled')
  ),

  origin_phase text,
  blocking_current_phase boolean not null default false,

  why_it_matters text,
  promoted_to_phase text,

  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  updated_at timestamptz not null default now()
);

create trigger trg_project_backlog_updated_at
before update on public.project_backlog
for each row execute function public.set_updated_at();

create index if not exists idx_backlog_project_status
  on public.project_backlog(project_key, status);

create index if not exists idx_backlog_blocking
  on public.project_backlog(project_key, blocking_current_phase);

-- ============================================================================
-- 14. DECISION LOG
-- ============================================================================

create table if not exists public.project_decisions (
  decision_id uuid primary key default gen_random_uuid(),
  project_key text not null default 'PMPD',

  decision_date timestamptz not null default now(),
  title text not null,
  decision text not null,

  rationale text,
  evidence text,

  affects_model_version text,
  supersedes_decision_id uuid references public.project_decisions(decision_id) on delete set null,

  status text not null default 'active' check (
    status in ('active','superseded','reversed')
  ),

  metadata_json jsonb not null default '{}'::jsonb
);

create index if not exists idx_decisions_project_date
  on public.project_decisions(project_key, decision_date desc);

-- ============================================================================
-- 15. CURRENT PROJECT STATE / DASHBOARD
-- ============================================================================

create table if not exists public.project_state (
  project_key text primary key,

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

create trigger trg_project_state_updated_at
before update on public.project_state
for each row execute function public.set_updated_at();

-- ============================================================================
-- 16. SEED PROGRAM PHASES
-- ============================================================================

insert into public.program_phases
(project_key, phase_code, phase_name, objective, status, sequence_order, exit_criteria, next_phase_code)
values
('PMPD','8H-1','Master Research Roadmap',
 'Create the authoritative PM+PD research-factor roadmap and governance rules.',
 'complete',1,
 'Roadmap approved and designated for Supabase source-of-truth storage.',
 '8H-2'),

('PMPD','8H-2','Research Factor & Data Dictionary',
 'Map planned research to signal-time/post-signal, raw/derived, source, resolution, and storage requirements.',
 'complete',2,
 'All roadmap families mapped to required data and timing constraints.',
 '8H-3'),

('PMPD','8H-3','Supabase Schema Design',
 'Design research + project-management schema before creating production research tables.',
 'active',3,
 'Schema reviewed, migration approved, and Migration 001 applied successfully.',
 '8H-4'),

('PMPD','8H-4','Historical Data Architecture',
 'Define Massive + TradingView + local canonical market-data architecture.',
 'ready',4,
 'Historical bar acquisition, caching, normalization, and reproducibility design approved.',
 '8H-5'),

('PMPD','8H-5','Frozen V4 Parity Specification',
 'Document the exact frozen V4 signal/classification/outcome logic the external engine must reproduce.',
 'backlog',5,
 'Parity spec complete and test fixtures identified.',
 '8H-6'),

('PMPD','8H-6','Historical Engine & Ingestion',
 'Build historical reconstruction and Supabase ingestion pipeline.',
 'backlog',6,
 'Pipeline can ingest canonical bars, reconstruct PM+PD candidates/signals, and write outcomes.',
 '8H-7'),

('PMPD','8H-7','Small-Sample Parity Validation',
 'Compare Python/Massive reconstruction against TradingView on a controlled sample.',
 'backlog',7,
 'Counts, timestamps, classifications, and outcomes reconcile within approved tolerance.',
 '8H-8'),

('PMPD','8H-8','112-Stock Historical Bootstrap',
 'Load the four 28-stock research sets into the versioned historical dataset.',
 'backlog',8,
 '112-stock bootstrap complete with coverage audit and no unresolved ingestion blockers.',
 '8H-9'),

('PMPD','8H-9','Expanded-Universe V4 Baseline Replication',
 'Re-test frozen V4 findings on the larger historical universe before optimization.',
 'backlog',9,
 'V4 baseline metrics replicated and differences documented.',
 '8H-10'),

('PMPD','8H-10','Individual-Factor Research',
 'Test signal-time factors individually before interaction mining.',
 'backlog',10,
 'Priority individual factors tested with N, breadth, robustness, and null findings recorded.',
 '8H-11'),

('PMPD','8H-11','Trade Health / Warning Research',
 'Develop evidence-based deterioration and W1/W2/W3 candidates.',
 'backlog',11,
 'Warning candidates tested for deterioration lift, recovery rate, and profile dependence.',
 '8H-12'),

('PMPD','8H-12','Controlled Interaction Research',
 'Test interactions only among factors with established individual evidence.',
 'backlog',12,
 'Interaction candidates evaluated without uncontrolled high-dimensional mining.',
 '8H-13'),

('PMPD','8H-13','Candidate V5 Model',
 'Build a candidate improvement to frozen V4 using only validated research findings.',
 'backlog',13,
 'Candidate model frozen with complete specification and expected trade-frequency impact.',
 '8H-14'),

('PMPD','8H-14','Holdout / Out-of-Sample Validation',
 'Validate V5 candidate against untouched data and compare directly with V4 baseline.',
 'backlog',14,
 'Holdout results complete with keep/adjust/reject decisions.',
 '8H-15'),

('PMPD','8H-15','Production Decision',
 'Decide whether to promote V5, retain V4, or continue research.',
 'backlog',15,
 'Production model/version decision recorded and deployment plan approved.',
 null)
on conflict (project_key, phase_code) do update
set
  phase_name = excluded.phase_name,
  objective = excluded.objective,
  status = excluded.status,
  sequence_order = excluded.sequence_order,
  exit_criteria = excluded.exit_criteria,
  next_phase_code = excluded.next_phase_code,
  updated_at = now();

-- ============================================================================
-- 17. SEED PROJECT DECISIONS
-- ============================================================================

insert into public.project_decisions
(project_key, title, decision, rationale, evidence, affects_model_version)
values
('PMPD',
 'Primary benchmark',
 '+0.50% favorable before -0.50% adverse remains the primary research benchmark.',
 'Maintains symmetric favorable/adverse comparison and direct comparability across research scenarios.',
 'Established throughout PM+PD historical research.',
 'V4'),

('PMPD',
 'Frozen V4 baseline',
 'V4 remains the baseline model during expanded research and must not be silently overwritten by later candidate models.',
 'Every proposed improvement must be measured against the same frozen reference model.',
 'Historical 16-stock research plus active forward-validation framework.',
 'V4'),

('PMPD',
 'Confirmation timeframe',
 '5-minute confirmation remains the frozen V4 baseline for parity and comparison work.',
 'Historical research favored 5-minute confirmation for filtering/quality despite later executable entry.',
 'Existing V4 research and forward-validation build.',
 'V4'),

('PMPD',
 'Supabase source of truth',
 'Supabase is the authoritative source of truth for the PM+PD roadmap, execution plan, experiments, decisions, and derived research data.',
 'Prevents roadmap drift, repeated work, and loss of experiment provenance.',
 'Project-management architecture approved 2026-08-28.',
 null),

('PMPD',
 'Tangent-management rule',
 'New ideas are captured immediately but do not interrupt the ACTIVE phase unless they expose a blocking data/design requirement.',
 'Preserves valuable ideas without allowing research tangents to derail the program plan.',
 'Project-management architecture approved 2026-08-28.',
 null),

('PMPD',
 'Separate Signal Quality and Trade Health',
 'Entry-known Signal Quality features and post-entry Trade Health/Warning features remain separate models and data domains.',
 'Prevents future information from leaking into signal-time research and supports cleaner model interpretation.',
 'Master roadmap architecture.',
 null),

('PMPD',
 'Raw-data retention principle',
 'Retain reproducible access to canonical 1-minute market data; do not rely only on currently qualifying signal rows.',
 'Allows future threshold changes, 2M/5M comparison, rejected-candidate analysis, and alternative model reconstruction.',
 'Research/Data Dictionary decision.',
 null),

('PMPD',
 'Initial raw-bar storage approach',
 'Do not load all raw Massive 1-minute bars into Supabase in Migration 001; cache raw bars externally and store reproducibility metadata plus derived PM+PD research rows in Supabase.',
 'Avoids unnecessary database volume while preserving reproducibility and future flexibility.',
 'Schema Design decision.',
 null);

-- ============================================================================
-- 18. SEED CURRENT PROJECT STATE
-- ============================================================================

insert into public.project_state
(
  project_key,
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
values
(
  'PMPD',
  '8H-3',
  'Supabase Schema Design',
  '8H-4',
  'Historical Data Architecture',
  0,
  'V4',
  'FROZEN_BASELINE',
  'IN_PROGRESS',
  'NOT_BUILT',
  0,
  'Supabase is the source of truth for roadmap, program plan, experiments, decisions, and derived PM+PD research data.',
  'PMPD-RM-1.0',
  jsonb_build_object(
    'historical_target_universe', 112,
    'stock_sets', 4,
    'stocks_per_set', 28,
    'primary_benchmark', '+0.50% before -0.50%',
    'baseline_confirmation_tf', '5m'
  )
)
on conflict (project_key) do update
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
-- 19. SEED MASTER RESEARCH FACTOR ROADMAP
--     PMPD-RM-1.0
-- ============================================================================

insert into public.research_factors
(project_key, factor_code, family, factor_name, priority, status, timing_type, data_type, implementation_status, finding, roadmap_version)
values
-- Family A: Setup / breakout quality
('PMPD','A01','A_SETUP_QUALITY','Breakout penetration beyond required PM/PD levels',1,'validated','signal_time','numeric','existing_v4','Core V4 signal-strength component; expanded-universe validation still required.','PMPD-RM-1.0'),
('PMPD','A02','A_SETUP_QUALITY','Breakout candle body-to-range ratio',1,'validated','signal_time','numeric','existing_v4','Core V4 signal-strength component; expanded-universe validation still required.','PMPD-RM-1.0'),
('PMPD','A03','A_SETUP_QUALITY','Strong-close / close-location percentage',1,'validated','signal_time','numeric','existing_v4','Core V4 signal-strength component; expanded-universe validation still required.','PMPD-RM-1.0'),
('PMPD','A04','A_SETUP_QUALITY','Breakout candle range vs ATR',1,'validated','signal_time','numeric','existing_v4','Core V4 signal-strength component; expanded-universe validation still required.','PMPD-RM-1.0'),
('PMPD','A05','A_SETUP_QUALITY','Directional candle quality',1,'validated','signal_time','boolean','existing_v4','Used in frozen V4 confirmation logic.','PMPD-RM-1.0'),
('PMPD','A06','A_SETUP_QUALITY','Breakout speed / velocity',1,'validated','signal_time','numeric','existing_v4','Confirmation speed is part of V4 classification.','PMPD-RM-1.0'),
('PMPD','A07','A_SETUP_QUALITY','Pre-signal 1-minute velocity',1,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','A08','A_SETUP_QUALITY','Pre-signal 2-minute velocity',1,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','A09','A_SETUP_QUALITY','Pre-signal 3-minute velocity',1,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','A10','A_SETUP_QUALITY','Pre-signal acceleration / deceleration',1,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','A11','A_SETUP_QUALITY','Distance between required PM/PD breakout levels',1,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','A12','A_SETUP_QUALITY','ATR-normalized distance between required levels',1,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','A13','A_SETUP_QUALITY','Which required level was crossed first',1,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','A14','A_SETUP_QUALITY','Time between first-level and second-level break',1,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','A15','A_SETUP_QUALITY','Distance traveled before final breakout / pre-signal extension',1,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','A16','A_SETUP_QUALITY','Volume at breakout',1,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','A17','A_SETUP_QUALITY','Relative-volume / volume expansion',1,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','A18','A_SETUP_QUALITY','Existing PM+PD Strength Score validation',1,'research_only','signal_time','composite','existing_v4','Historically useful, but larger 112-stock validation is pending.','PMPD-RM-1.0'),
('PMPD','A19','A_SETUP_QUALITY','Existing Grade validation',1,'research_only','signal_time','categorical','existing_v4','Grade alone was not a sufficient quality ranking; Grade x Profile interaction matters.','PMPD-RM-1.0'),
('PMPD','A20','A_SETUP_QUALITY','Existing V4 Profile validation',1,'research_only','signal_time','categorical','existing_v4','V4 materially reduced Unclassified population and created distinct behavioral groups in the 16-stock sample.','PMPD-RM-1.0'),
('PMPD','A21','A_SETUP_QUALITY','Grade x V4 Profile validation',1,'research_only','signal_time','interaction','existing_v4','Core production lookup is based on Grade x Profile; expanded-universe validation pending.','PMPD-RM-1.0'),
('PMPD','A22','A_SETUP_QUALITY','PRIME vs CONDITIONAL vs suppressed populations',1,'testing','signal_time','categorical','existing_v4','Frozen forward validation currently testing whether production priorities generalize.','PMPD-RM-1.0'),
('PMPD','A23','A_SETUP_QUALITY','EXPANSION vs SCALP behavior',1,'testing','signal_time','categorical','existing_v4','Historical data suggested different MFE/MAE behavior; forward validation ongoing.','PMPD-RM-1.0'),

-- Family B: Stock context
('PMPD','B01','B_STOCK_CONTEXT','Previous-day stock candle direction',2,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','B02','B_STOCK_CONTEXT','Previous-day stock return magnitude',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B03','B_STOCK_CONTEXT','Previous-day candle body strength',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B04','B_STOCK_CONTEXT','Previous-day candle range',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B05','B_STOCK_CONTEXT','Previous-day range normalized by ATR',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B06','B_STOCK_CONTEXT','Previous-day close location',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B07','B_STOCK_CONTEXT','Previous-day candle strength composite',2,'not_tested','signal_time','composite','planned',null,'PMPD-RM-1.0'),
('PMPD','B08','B_STOCK_CONTEXT','Stock 3-day trend',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B09','B_STOCK_CONTEXT','Stock 5-day trend',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B10','B_STOCK_CONTEXT','Stock 10-day trend',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B11','B_STOCK_CONTEXT','Stock 20-day trend',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B12','B_STOCK_CONTEXT','Multi-day trend strength / slope',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B13','B_STOCK_CONTEXT','HH/HL vs LH/LL structure',2,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','B14','B_STOCK_CONTEXT','Higher-timeframe moving-average position / slope',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B15','B_STOCK_CONTEXT','Weekly symbol bias',2,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','B16','B_STOCK_CONTEXT','Weekly-bias strength',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B17','B_STOCK_CONTEXT','Signal x weekly-bias alignment',2,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','B18','B_STOCK_CONTEXT','Gap direction',2,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','B19','B_STOCK_CONTEXT','Gap magnitude',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B20','B_STOCK_CONTEXT','Gap alignment with breakout',2,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','B21','B_STOCK_CONTEXT','Premarket direction / trend',2,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','B22','B_STOCK_CONTEXT','Premarket move magnitude',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B23','B_STOCK_CONTEXT','Premarket range',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B24','B_STOCK_CONTEXT','Premarket position relative to previous-day levels',2,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','B25','B_STOCK_CONTEXT','Distance from VWAP at signal',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B26','B_STOCK_CONTEXT','VWAP slope at signal',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B27','B_STOCK_CONTEXT','Signal direction vs VWAP side',2,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','B28','B_STOCK_CONTEXT','ATR-normalized extension from VWAP',2,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','B29','B_STOCK_CONTEXT','ATR / volatility regime',2,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','B30','B_STOCK_CONTEXT','Normal intraday volatility regime',2,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),

-- Family C: Market context
('PMPD','C01','C_MARKET_CONTEXT','Previous-day SPY direction / return',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C02','C_MARKET_CONTEXT','Previous-day QQQ direction / return',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C03','C_MARKET_CONTEXT','Previous-day DIA direction / return',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C04','C_MARKET_CONTEXT','Previous-day 3-index agreement',3,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','C05','C_MARKET_CONTEXT','Previous-day Bullish/Bearish/Mixed regime',3,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','C06','C_MARKET_CONTEXT','SPY/QQQ/DIA 3-day trends',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C07','C_MARKET_CONTEXT','Aggregate 3-day market trend',3,'not_tested','signal_time','composite','planned',null,'PMPD-RM-1.0'),
('PMPD','C08','C_MARKET_CONTEXT','SPY/QQQ/DIA 5-day trends',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C09','C_MARKET_CONTEXT','SPY/QQQ/DIA 10-day trends',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C10','C_MARKET_CONTEXT','SPY/QQQ/DIA 20-day trends',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C11','C_MARKET_CONTEXT','Multi-day market trend strength',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C12','C_MARKET_CONTEXT','Current-day SPY direction at signal',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C13','C_MARKET_CONTEXT','Current-day QQQ direction at signal',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C14','C_MARKET_CONTEXT','Current-day DIA direction at signal',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C15','C_MARKET_CONTEXT','Current-day 3-index agreement',3,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','C16','C_MARKET_CONTEXT','Current market bias',3,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','C17','C_MARKET_CONTEXT','Signal x market-bias alignment',3,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','C18','C_MARKET_CONTEXT','Current market move magnitude',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C19','C_MARKET_CONTEXT','Market velocity into signal',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C20','C_MARKET_CONTEXT','Market acceleration / deceleration',3,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','C21','C_MARKET_CONTEXT','Broad-market volatility regime',3,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),

-- Family D: Relative / alignment
('PMPD','D01','D_RELATIVE_ALIGNMENT','Signal vs previous-day market regime',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D02','D_RELATIVE_ALIGNMENT','Signal vs current market regime',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D03','D_RELATIVE_ALIGNMENT','Signal vs previous-day stock direction',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D04','D_RELATIVE_ALIGNMENT','Signal vs multi-day stock trend',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D05','D_RELATIVE_ALIGNMENT','Signal vs weekly stock bias',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D06','D_RELATIVE_ALIGNMENT','Stock trend vs market trend alignment',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D07','D_RELATIVE_ALIGNMENT','Stock vs SPY relative strength / weakness',4,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','D08','D_RELATIVE_ALIGNMENT','Stock vs QQQ relative strength / weakness',4,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','D09','D_RELATIVE_ALIGNMENT','Relative strength / weakness persistence',4,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','D10','D_RELATIVE_ALIGNMENT','Sector direction at signal',4,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','D11','D_RELATIVE_ALIGNMENT','Stock vs sector relative strength',4,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','D12','D_RELATIVE_ALIGNMENT','Stock x sector alignment',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D13','D_RELATIVE_ALIGNMENT','Sector x market alignment',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D14','D_RELATIVE_ALIGNMENT','Stock + sector + market three-way alignment',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D15','D_RELATIVE_ALIGNMENT','Gap + stock trend + signal alignment',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D16','D_RELATIVE_ALIGNMENT','Previous-day stock + previous-day market alignment',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D17','D_RELATIVE_ALIGNMENT','Setup strength + market regime',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D18','D_RELATIVE_ALIGNMENT','Setup strength + stock trend',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D19','D_RELATIVE_ALIGNMENT','Setup strength + relative strength',4,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','D20','D_RELATIVE_ALIGNMENT','Pre-signal context vs subsequent warning probability',4,'not_tested','mixed','interaction','planned',null,'PMPD-RM-1.0'),

-- Family E: Post-signal Trade Health / W-system
('PMPD','E01','E_TRADE_HEALTH','Favorable separation after signal',5,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','E02','E_TRADE_HEALTH','Time to first favorable progress',5,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','E03','E_TRADE_HEALTH','Time without new favorable extreme',5,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','E04','E_TRADE_HEALTH','MFE trajectory',5,'not_tested','post_signal','trajectory','planned',null,'PMPD-RM-1.0'),
('PMPD','E05','E_TRADE_HEALTH','MAE trajectory',5,'not_tested','post_signal','trajectory','planned',null,'PMPD-RM-1.0'),
('PMPD','E06','E_TRADE_HEALTH','MFE/MAE relationship through time',5,'not_tested','post_signal','trajectory','planned',null,'PMPD-RM-1.0'),
('PMPD','E07','E_TRADE_HEALTH','Confirmation-candle retracement',5,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','E08','E_TRADE_HEALTH','Post-breakout impulse retracement',5,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','E09','E_TRADE_HEALTH','Fib 23.6% retracement',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E10','E_TRADE_HEALTH','Fib 38.2% retracement',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E11','E_TRADE_HEALTH','Fib 50% retracement',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E12','E_TRADE_HEALTH','Fib 61.8% retracement',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E13','E_TRADE_HEALTH','Fib 78.6% retracement',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E14','E_TRADE_HEALTH','PM/PD breakout-level loss',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E15','E_TRADE_HEALTH','Loss of one required breakout level',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E16','E_TRADE_HEALTH','Loss of both required breakout levels',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E17','E_TRADE_HEALTH','Close back inside breakout structure',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E18','E_TRADE_HEALTH','Breakout level reclaim after failure',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E19','E_TRADE_HEALTH','VWAP loss against trade',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E20','E_TRADE_HEALTH','VWAP reclaim',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E21','E_TRADE_HEALTH','VWAP lost/not-reclaimed state',5,'not_tested','post_signal','state','planned',null,'PMPD-RM-1.0'),
('PMPD','E22','E_TRADE_HEALTH','Consecutive adverse candles',5,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','E23','E_TRADE_HEALTH','Momentum deterioration',5,'not_tested','post_signal','state','planned',null,'PMPD-RM-1.0'),
('PMPD','E24','E_TRADE_HEALTH','Speed of deterioration',5,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','E25','E_TRADE_HEALTH','Warning persistence / duration',5,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','E26','E_TRADE_HEALTH','Recovery after warning',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E27','E_TRADE_HEALTH','MAE progression milestones',5,'not_tested','post_signal','event','planned',null,'PMPD-RM-1.0'),
('PMPD','E28','E_TRADE_HEALTH','Profile-aware deterioration',5,'not_tested','post_signal','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','E29','E_TRADE_HEALTH','PRIME vs CONDITIONAL deterioration',5,'not_tested','post_signal','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','E30','E_TRADE_HEALTH','EXPANSION vs SCALP deterioration',5,'not_tested','post_signal','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','E31','E_TRADE_HEALTH','Candidate W1 severity',5,'not_tested','post_signal','state','planned',null,'PMPD-RM-1.0'),
('PMPD','E32','E_TRADE_HEALTH','Candidate W2 severity',5,'not_tested','post_signal','state','planned',null,'PMPD-RM-1.0'),
('PMPD','E33','E_TRADE_HEALTH','Candidate W3 severity',5,'not_tested','post_signal','state','planned',null,'PMPD-RM-1.0'),
('PMPD','E34','E_TRADE_HEALTH','Probability of eventual +0.50% success after warning',5,'not_tested','post_signal','outcome','planned',null,'PMPD-RM-1.0'),
('PMPD','E35','E_TRADE_HEALTH','False-warning / recovery rate',5,'not_tested','post_signal','outcome','planned',null,'PMPD-RM-1.0'),

-- Family F: Time / execution
('PMPD','F01','F_TIME_EXECUTION','Time-of-day signal performance',6,'ready','signal_time','categorical','research_build_ready','Dedicated Time-of-Day Research build exists; pooled study not yet completed.','PMPD-RM-1.0'),
('PMPD','F02','F_TIME_EXECUTION','Minutes since RTH open',6,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','F03','F_TIME_EXECUTION','Early vs middle vs late RTH',6,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','F04','F_TIME_EXECUTION','Time x direction',6,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','F05','F_TIME_EXECUTION','Time x PRIME/CONDITIONAL',6,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','F06','F_TIME_EXECUTION','Time x EXPANSION/SCALP',6,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','F07','F_TIME_EXECUTION','Time x market regime',6,'not_tested','signal_time','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','F08','F_TIME_EXECUTION','Day of week',6,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','F09','F_TIME_EXECUTION','Month / seasonality',6,'not_tested','signal_time','categorical','planned',null,'PMPD-RM-1.0'),
('PMPD','F10','F_TIME_EXECUTION','5-minute confirmation lag',6,'not_tested','mixed','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','F11','F_TIME_EXECUTION','Favorable move consumed before alert',6,'not_tested','mixed','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','F12','F_TIME_EXECUTION','Executable price vs confirmation reference price',6,'not_tested','mixed','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','F13','F_TIME_EXECUTION','2-minute vs 5-minute confirmation',6,'research_only','mixed','comparison','planned','Prior research favored 5-minute confirmation; expanded-universe executable-entry analysis is still pending.','PMPD-RM-1.0'),
('PMPD','F14','F_TIME_EXECUTION','1M/2M/3M/5M confirmation comparison',6,'not_tested','mixed','comparison','planned',null,'PMPD-RM-1.0'),
('PMPD','F15','F_TIME_EXECUTION','Signal quality vs entry latency tradeoff',6,'not_tested','mixed','interaction','planned',null,'PMPD-RM-1.0'),

-- Family G: Symbol / universe
('PMPD','G01','G_SYMBOL_UNIVERSE','Overall performance by symbol',7,'ready','static','categorical','planned','Original 16-stock data exists but final reusable symbol ranking was not preserved.','PMPD-RM-1.0'),
('PMPD','G02','G_SYMBOL_UNIVERSE','Bull performance by symbol',7,'ready','static','categorical','planned','Top-5 bullish ranking requested; expanded event-level DB will support it.','PMPD-RM-1.0'),
('PMPD','G03','G_SYMBOL_UNIVERSE','Bear performance by symbol',7,'ready','static','categorical','planned','Top-5 bearish ranking requested; expanded event-level DB will support it.','PMPD-RM-1.0'),
('PMPD','G04','G_SYMBOL_UNIVERSE','PRIME performance by symbol',7,'not_tested','static','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','G05','G_SYMBOL_UNIVERSE','CONDITIONAL performance by symbol',7,'not_tested','static','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','G06','G_SYMBOL_UNIVERSE','EXPANSION performance by symbol',7,'not_tested','static','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','G07','G_SYMBOL_UNIVERSE','SCALP performance by symbol',7,'not_tested','static','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','G08','G_SYMBOL_UNIVERSE','Symbol x direction',7,'not_tested','static','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','G09','G_SYMBOL_UNIVERSE','Symbol x Grade/Profile',7,'not_tested','static','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','G10','G_SYMBOL_UNIVERSE','Symbol x market regime',7,'not_tested','static','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','G11','G_SYMBOL_UNIVERSE','Symbol x time of day',7,'not_tested','static','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','G12','G_SYMBOL_UNIVERSE','Recent symbol-performance changes',7,'not_tested','static','trajectory','planned',null,'PMPD-RM-1.0'),
('PMPD','G13','G_SYMBOL_UNIVERSE','Performance stability through time',7,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','G14','G_SYMBOL_UNIVERSE','Sample maturity / N',7,'research_only','static','numeric','existing_research','Confidence rules already separate sample size from observed quality.','PMPD-RM-1.0'),
('PMPD','G15','G_SYMBOL_UNIVERSE','Stock volatility characteristics',7,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','G16','G_SYMBOL_UNIVERSE','Stock liquidity characteristics',7,'not_tested','signal_time','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','G17','G_SYMBOL_UNIVERSE','Performance clusters by stock characteristics',7,'not_tested','static','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','G18','G_SYMBOL_UNIVERSE','Original 16-stock vs expanded 112-stock universe',7,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','G19','G_SYMBOL_UNIVERSE','Cross-universe robustness',7,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),

-- Family H: Outcome / target optimization
('PMPD','H01','H_OUTCOME_TARGETS','+0.25% favorable-first',8,'not_tested','post_signal','outcome','planned',null,'PMPD-RM-1.0'),
('PMPD','H02','H_OUTCOME_TARGETS','+0.50% favorable-first',8,'validated','post_signal','outcome','existing_v4','Primary benchmark.','PMPD-RM-1.0'),
('PMPD','H03','H_OUTCOME_TARGETS','+0.75% favorable-first',8,'not_tested','post_signal','outcome','planned',null,'PMPD-RM-1.0'),
('PMPD','H04','H_OUTCOME_TARGETS','+1.00% favorable hit',8,'validated','post_signal','outcome','existing_v4','Secondary continuation benchmark used throughout V4 research.','PMPD-RM-1.0'),
('PMPD','H05','H_OUTCOME_TARGETS','MFE distribution percentiles',8,'not_tested','post_signal','distribution','planned',null,'PMPD-RM-1.0'),
('PMPD','H06','H_OUTCOME_TARGETS','MAE distribution percentiles',8,'not_tested','post_signal','distribution','planned',null,'PMPD-RM-1.0'),
('PMPD','H07','H_OUTCOME_TARGETS','Time to +0.25%',8,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','H08','H_OUTCOME_TARGETS','Time to +0.50%',8,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','H09','H_OUTCOME_TARGETS','Time to +0.75%',8,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','H10','H_OUTCOME_TARGETS','Time to +1.00%',8,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','H11','H_OUTCOME_TARGETS','Time to adverse milestones',8,'not_tested','post_signal','numeric','planned',null,'PMPD-RM-1.0'),
('PMPD','H12','H_OUTCOME_TARGETS','Same-bar favorable/adverse cases',8,'research_only','post_signal','outcome','existing_v4','Same-bar cases are already recognized but deserve larger-dataset treatment.','PMPD-RM-1.0'),
('PMPD','H13','H_OUTCOME_TARGETS','EXPANSION-specific targets',8,'not_tested','post_signal','optimization','planned',null,'PMPD-RM-1.0'),
('PMPD','H14','H_OUTCOME_TARGETS','SCALP-specific targets',8,'not_tested','post_signal','optimization','planned',null,'PMPD-RM-1.0'),
('PMPD','H15','H_OUTCOME_TARGETS','Structural exits vs fixed exits',8,'not_tested','post_signal','comparison','planned',null,'PMPD-RM-1.0'),

-- Family I: Interactions / model development
('PMPD','I01','I_MODEL_INTERACTIONS','Grade x Profile x Time',9,'not_tested','mixed','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','I02','I_MODEL_INTERACTIONS','Grade x Profile x Market Bias',9,'not_tested','mixed','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','I03','I_MODEL_INTERACTIONS','Grade x Profile x Weekly Bias',9,'not_tested','mixed','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','I04','I_MODEL_INTERACTIONS','Grade x Profile x Relative Strength',9,'not_tested','mixed','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','I05','I_MODEL_INTERACTIONS','Market x Weekly alignment',9,'not_tested','mixed','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','I06','I_MODEL_INTERACTIONS','Time x Market Bias',9,'not_tested','mixed','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','I07','I_MODEL_INTERACTIONS','Volatility x Profile',9,'not_tested','mixed','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','I08','I_MODEL_INTERACTIONS','Symbol characteristics x Profile',9,'not_tested','mixed','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','I09','I_MODEL_INTERACTIONS','Setup quality x warning probability',9,'not_tested','mixed','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','I10','I_MODEL_INTERACTIONS','Signal context x warning recovery',9,'not_tested','mixed','interaction','planned',null,'PMPD-RM-1.0'),
('PMPD','I11','I_MODEL_INTERACTIONS','Minimal-factor model development',9,'not_tested','mixed','model','planned',null,'PMPD-RM-1.0'),
('PMPD','I12','I_MODEL_INTERACTIONS','Complexity vs V4 baseline improvement',9,'not_tested','mixed','model','planned',null,'PMPD-RM-1.0'),
('PMPD','I13','I_MODEL_INTERACTIONS','Signal-frequency cost of added filters',9,'not_tested','mixed','model','planned',null,'PMPD-RM-1.0'),

-- Family J: Robustness / validation
('PMPD','J01','J_ROBUSTNESS','Discovery vs holdout datasets',10,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','J02','J_ROBUSTNESS','Older vs newer periods',10,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','J03','J_ROBUSTNESS','Bull vs Bear robustness',10,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','J04','J_ROBUSTNESS','Market-regime robustness',10,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','J05','J_ROBUSTNESS','Volatility-regime robustness',10,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','J06','J_ROBUSTNESS','Cross-symbol robustness',10,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','J07','J_ROBUSTNESS','Cross-stock-set robustness',10,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','J08','J_ROBUSTNESS','Across-year robustness',10,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','J09','J_ROBUSTNESS','Threshold sensitivity',10,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','J10','J_ROBUSTNESS','Nearby-parameter stability',10,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','J11','J_ROBUSTNESS','Original 16 vs 112-stock universe',10,'not_tested','static','robustness','planned',null,'PMPD-RM-1.0'),
('PMPD','J12','J_ROBUSTNESS','Frozen candidate out-of-sample test',10,'not_tested','static','validation','planned',null,'PMPD-RM-1.0'),
('PMPD','J13','J_ROBUSTNESS','Forward validation',10,'testing','static','validation','existing_v4','Frozen V4 forward validation is currently underway.','PMPD-RM-1.0'),
('PMPD','J14','J_ROBUSTNESS','Optimized candidate vs frozen V4 baseline',10,'not_tested','static','validation','planned',null,'PMPD-RM-1.0')
on conflict (project_key, factor_code) do update
set
  family = excluded.family,
  factor_name = excluded.factor_name,
  priority = excluded.priority,
  status = excluded.status,
  timing_type = excluded.timing_type,
  data_type = excluded.data_type,
  implementation_status = excluded.implementation_status,
  finding = excluded.finding,
  roadmap_version = excluded.roadmap_version,
  updated_at = now();

-- ============================================================================
-- 20. OPTIONAL VIEW: PROJECT DASHBOARD
-- ============================================================================

create or replace view public.v_pm_pd_project_dashboard as
select
  ps.project_key,
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
    where rf.project_key = ps.project_key
  ) as total_research_factors,
  (
    select count(*)
    from public.research_factors rf
    where rf.project_key = ps.project_key
      and rf.status in ('validated','production_candidate')
  ) as validated_research_factors,
  (
    select count(*)
    from public.project_backlog pb
    where pb.project_key = ps.project_key
      and pb.status not in ('complete','rejected','cancelled')
  ) as open_backlog_items
from public.project_state ps
where ps.project_key = 'PMPD';

-- ============================================================================
-- 21. ROW LEVEL SECURITY
-- ============================================================================
--
-- Enable RLS on project/research tables. Backend ingestion should use the
-- Supabase service_role key (server-side only), which bypasses RLS.
-- No public/anon policies are created in Migration 001.
-- Add authenticated-user policies later when we build a UI/dashboard.
-- ============================================================================

alter table public.datasets enable row level security;
alter table public.research_runs enable row level security;
alter table public.symbols enable row level security;
alter table public.pm_pd_candidates enable row level security;
alter table public.pm_pd_signals enable row level security;
alter table public.pm_pd_signal_features enable row level security;
alter table public.symbol_context enable row level security;
alter table public.market_context enable row level security;
alter table public.pm_pd_outcomes enable row level security;
alter table public.pm_pd_post_signal_events enable row level security;
alter table public.program_phases enable row level security;
alter table public.research_factors enable row level security;
alter table public.research_experiments enable row level security;
alter table public.project_backlog enable row level security;
alter table public.project_decisions enable row level security;
alter table public.project_state enable row level security;

-- ============================================================================
-- END MIGRATION 001
-- ============================================================================
