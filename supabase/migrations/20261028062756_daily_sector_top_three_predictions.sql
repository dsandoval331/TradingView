-- Immutable forecast snapshots; separate first-verified daily closing outcomes.
create table public.sector_top3_predictions (
 target_date date not null,
 stage text not null check (stage in ('overnight','premarket','open30')),
 symbol text not null check (symbol in ('XLE','XLV','XLK')),
 recorded_at timestamptz not null default now(),
 data_as_of timestamptz not null,
 top3 numeric not null check (top3 between 0 and 100),
 middle numeric not null check (middle between 0 and 100),
 bottom3 numeric not null check (bottom3 between 0 and 100),
 confidence text not null check (confidence in ('Low','Medium','High')),
 reason text not null check (length(reason)>0),
 sources jsonb not null check (jsonb_typeof(sources)='array'),
 methodology text not null default 'judgment-v1' check (methodology='judgment-v1'),
 availability text not null default 'researched' check (availability in ('researched','baseline_only')),
 primary key (target_date,stage,symbol),
 check (top3+middle+bottom3=100),
 check (data_as_of<=recorded_at),
 check ((recorded_at at time zone 'America/New_York')::date=target_date),
 check (extract(isodow from target_date)<6),
 check ((stage in ('overnight','premarket') and recorded_at<((target_date+time '09:30') at time zone 'America/New_York') and data_as_of<((target_date+time '09:30') at time zone 'America/New_York')) or (stage='open30' and recorded_at>=((target_date+time '10:00') at time zone 'America/New_York') and recorded_at<((target_date+time '11:00') at time zone 'America/New_York') and data_as_of<=((target_date+time '10:00') at time zone 'America/New_York')))
);
create table public.sector_top3_results (
 target_date date primary key,
 recorded_at timestamptz not null default now(),
 payload jsonb not null check (jsonb_typeof(payload)='object'),
 check (recorded_at>=((target_date+time '16:00') at time zone 'America/New_York'))
);
alter table public.sector_top3_predictions enable row level security;
alter table public.sector_top3_results enable row level security;
revoke all on public.sector_top3_predictions,public.sector_top3_results from public,anon,authenticated,service_role;
grant select on public.sector_top3_predictions,public.sector_top3_results to authenticated;
grant select on public.sector_top3_predictions,public.sector_top3_results to service_role;
grant insert (target_date,stage,symbol,data_as_of,top3,middle,bottom3,confidence,reason,sources,methodology,availability) on public.sector_top3_predictions to service_role;
grant insert (target_date,payload) on public.sector_top3_results to service_role;
create policy sector_top3_predictions_allowlist on public.sector_top3_predictions for select to authenticated using ((select public.is_trading_research_web_user()));
create policy sector_top3_results_allowlist on public.sector_top3_results for select to authenticated using ((select public.is_trading_research_web_user()));
comment on table public.sector_top3_predictions is 'Recorded analyst probability snapshots for XLE/XLV/XLK versus all eleven sectors. No retrospective forecast backfill; uncalibrated judgment-v1.';
comment on table public.sector_top3_results is 'Append-only first verified closing ranks; daily-return descending, ticker ascending for exact ties; independent of heatmap settings.';
