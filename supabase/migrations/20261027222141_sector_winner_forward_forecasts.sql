-- Tracker-only forward snapshots. Browser clients are read-only under the existing allowlist.
create table public.sector_winner_forecasts (
 id text primary key,
 version text not null,
 source_date date not null,
 recorded_at timestamptz not null default now(),
 payload jsonb not null,
 unique(version,source_date),
 check (jsonb_typeof(payload)='object'),
 check (source_date < (recorded_at at time zone 'America/New_York')::date),
 check ((recorded_at at time zone 'America/New_York')::time < time '08:00')
);
create table public.sector_winner_forecast_results (
 forecast_id text primary key references public.sector_winner_forecasts(id),
 target_date date not null,
 recorded_at timestamptz not null default now(),
 payload jsonb not null,
 check (jsonb_typeof(payload)='object'),
 check (recorded_at >= ((target_date+time '16:00') at time zone 'America/New_York'))
);
alter table public.sector_winner_forecasts enable row level security;
alter table public.sector_winner_forecast_results enable row level security;
revoke all on public.sector_winner_forecasts,public.sector_winner_forecast_results from public,anon,authenticated,service_role;
grant select on public.sector_winner_forecasts,public.sector_winner_forecast_results to authenticated;
grant select,insert on public.sector_winner_forecasts,public.sector_winner_forecast_results to service_role;
create policy sector_winner_forecasts_allowlist on public.sector_winner_forecasts for select to authenticated using ((select public.is_trading_research_web_user()));
create policy sector_winner_forecast_results_allowlist on public.sector_winner_forecast_results for select to authenticated using ((select public.is_trading_research_web_user()));
comment on table public.sector_winner_forecasts is 'Immutable-by-application-role pre-open next-session sector picks. Experimental descriptive model, no broker orders.';
comment on table public.sector_winner_forecast_results is 'One appended outcome per forecast; original forecast cannot be updated by application roles.';
