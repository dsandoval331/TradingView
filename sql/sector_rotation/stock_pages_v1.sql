-- MWE-SECTOR-STOCKS-001 | Tool: Sector Rotation Tracker
-- Additive, isolated from all frozen research datasets.
create table public.stock_tracker_runs (
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
create table public.stock_daily_observations (
  run_id uuid not null references public.stock_tracker_runs(run_id),
  symbol text not null check (symbol ~ '^[A-Z][A-Z0-9.-]{0,9}$'),
  trade_date date not null,
  close numeric not null check (close > 0),
  open numeric not null,
  high numeric not null,
  low numeric not null check (low>0),
  check (high>=greatest(open,close) and low<=least(open,close) and high<'Infinity'::numeric),
  volume numeric not null check (volume >= 0),
  response_sha256 text not null check (response_sha256 ~ '^[0-9a-f]{64}$'),
  primary key (run_id,symbol,trade_date)
);
create index stock_obs_symbol_date on public.stock_daily_observations(symbol,trade_date desc);
create index stock_runs_completed on public.stock_tracker_runs(completed_at desc) where status='COMPLETE';
alter table public.stock_tracker_runs enable row level security;
alter table public.stock_daily_observations enable row level security;
revoke all on public.stock_tracker_runs,public.stock_daily_observations from anon,authenticated;
grant select on public.stock_tracker_runs,public.stock_daily_observations to authenticated;
grant all on public.stock_tracker_runs,public.stock_daily_observations to service_role;
create policy stock_runs_allowlist_read on public.stock_tracker_runs for select to authenticated using ((select public.is_trading_research_web_user()));
create policy stock_obs_allowlist_read on public.stock_daily_observations for select to authenticated using ((select public.is_trading_research_web_user()));
-- Failed/in-progress collections never replace published prices.
create view public.v_stock_daily_latest with (security_invoker=true) as
select distinct on (o.symbol,o.trade_date) o.symbol,o.trade_date,o.close,o.volume,o.run_id,r.completed_at as collected_at,o.response_sha256,o.open,o.high,o.low
from public.stock_daily_observations o join public.stock_tracker_runs r using (run_id)
where r.status='COMPLETE'
order by o.symbol,o.trade_date,r.completed_at desc,r.run_id;
revoke all on public.v_stock_daily_latest from anon,authenticated;
grant select on public.v_stock_daily_latest to authenticated,service_role;
comment on view public.v_stock_daily_latest is 'Sector tracker only. Latest successful observations; split-adjusted price, not dividends or measured fund flows. Authenticated MULtipLY allowlist required.';

create table public.stock_tracker_symbols (
 symbol text primary key check (symbol ~ '^[A-Z][A-Z0-9.-]{0,9}$'),
 requested_at timestamptz not null default now(),
 last_success_at timestamptz,
 last_error text
);
alter table public.stock_tracker_symbols enable row level security;
revoke all on public.stock_tracker_symbols from anon,authenticated;
grant select on public.stock_tracker_symbols to authenticated;
grant insert(symbol) on public.stock_tracker_symbols to authenticated;
grant all on public.stock_tracker_symbols to service_role;
create policy stock_symbols_read on public.stock_tracker_symbols for select to authenticated using ((select public.is_trading_research_web_user()));
create policy stock_symbols_request on public.stock_tracker_symbols for insert to authenticated with check ((select public.is_trading_research_web_user()));
insert into public.stock_tracker_symbols(symbol) values ('SPY'),('MSFT'),('AAPL'),('NVDA'),('TSLA'),('AMD');
