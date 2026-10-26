-- MWE-SECTOR-V1-001 | Tool: Sector Rotation Tracker
-- Additive, isolated from all frozen research datasets.
create table public.sector_tracker_runs (
  run_id uuid primary key,
  work_envelope_id uuid not null references public.work_envelopes(work_envelope_id),
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null check (status in ('RUNNING','COMPLETE','FAILED')),
  source text not null default 'massive',
  adjustment text not null default 'split_adjusted_price_not_total_return',
  git_sha text not null check (git_sha ~ '^[0-9a-f]{40}$'),
  external_run_id text not null,
  requested_start date not null,
  requested_end date not null,
  latest_session date,
  observation_count integer not null default 0,
  metadata_json jsonb not null default '{}'::jsonb
);
create table public.sector_daily_observations (
  run_id uuid not null references public.sector_tracker_runs(run_id),
  symbol text not null check (symbol in ('SPY','XLB','XLC','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY')),
  trade_date date not null,
  close numeric not null check (close > 0),
  volume numeric not null check (volume >= 0),
  response_sha256 text not null check (response_sha256 ~ '^[0-9a-f]{64}$'),
  primary key (run_id,symbol,trade_date)
);
create index sector_obs_symbol_date on public.sector_daily_observations(symbol,trade_date desc);
create index sector_runs_completed on public.sector_tracker_runs(completed_at desc) where status='COMPLETE';
alter table public.sector_tracker_runs enable row level security;
alter table public.sector_daily_observations enable row level security;
revoke all on public.sector_tracker_runs,public.sector_daily_observations from anon,authenticated;
grant select on public.sector_tracker_runs,public.sector_daily_observations to authenticated;
grant all on public.sector_tracker_runs,public.sector_daily_observations to service_role;
create policy sector_runs_allowlist_read on public.sector_tracker_runs for select to authenticated using ((select public.is_trading_research_web_user()));
create policy sector_obs_allowlist_read on public.sector_daily_observations for select to authenticated using ((select public.is_trading_research_web_user()));
-- Failed/in-progress collections never replace published prices.
create view public.v_sector_daily_latest with (security_invoker=true) as
select distinct on (o.symbol,o.trade_date) o.symbol,o.trade_date,o.close,o.volume,o.run_id,r.completed_at as collected_at,o.response_sha256
from public.sector_daily_observations o join public.sector_tracker_runs r using (run_id)
where r.status='COMPLETE'
order by o.symbol,o.trade_date,r.completed_at desc,r.run_id;
revoke all on public.v_sector_daily_latest from anon,authenticated;
grant select on public.v_sector_daily_latest to authenticated,service_role;
comment on view public.v_sector_daily_latest is 'Sector tracker only. Latest successful observations; split-adjusted price, not dividends or measured fund flows. Authenticated MULtipLY allowlist required.';
