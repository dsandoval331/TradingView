-- MWE-SECTOR-CANDLES-001 | Tool: Sector Rotation Tracker
-- Nullable OHLC preserves old append-only observations. No access changes.
alter table public.sector_daily_observations
  add column open numeric,
  add column high numeric,
  add column low numeric,
  add constraint sector_ohlc_valid check (
    (open is null and high is null and low is null) or
    (open is not null and high is not null and low is not null
     and low > 0 and high >= greatest(open,close) and low <= least(open,close)
     and high < 'Infinity'::numeric)
  );
create or replace view public.v_sector_daily_latest with (security_invoker=true) as
select distinct on (o.symbol,o.trade_date) o.symbol,o.trade_date,o.close,o.volume,o.run_id,r.completed_at as collected_at,o.response_sha256,o.open,o.high,o.low
from public.sector_daily_observations o join public.sector_tracker_runs r using (run_id)
where r.status='COMPLETE'
order by o.symbol,o.trade_date,r.completed_at desc,r.run_id;
alter table public.tech_daily_observations
  add column open numeric,
  add column high numeric,
  add column low numeric,
  add constraint tech_ohlc_valid check (
    (open is null and high is null and low is null) or
    (open is not null and high is not null and low is not null
     and low > 0 and high >= greatest(open,close) and low <= least(open,close)
     and high < 'Infinity'::numeric)
  );
create or replace view public.v_tech_daily_latest with (security_invoker=true) as
select distinct on (o.symbol,o.trade_date) o.symbol,o.trade_date,o.close,o.volume,o.run_id,r.completed_at as collected_at,o.response_sha256,o.open,o.high,o.low
from public.tech_daily_observations o join public.tech_tracker_runs r using (run_id)
where r.status='COMPLETE'
order by o.symbol,o.trade_date,r.completed_at desc,r.run_id;
