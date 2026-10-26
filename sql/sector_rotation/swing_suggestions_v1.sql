-- MWE-SECTOR-METHOD2-BACKFILL-001 | additive tracker-only snapshot storage.
create table public.sector_swing_suggestions (
 id text primary key,
 method_id integer not null check(method_id in (1,2)),
 method_version text not null,
 symbol text not null check(symbol ~ '^[A-Z][A-Z0-9.-]{0,9}$'),
 suggested_date date not null,
 side text not null check(side in ('long','short')),
 entry_price numeric not null check(entry_price>0 and entry_price<'Infinity'::numeric),
 reason text not null check(length(trim(reason))>0),
 origin text not null check(origin in ('retrospective','recorded')),
 recorded_at timestamptz not null default now(),
 metadata_json jsonb not null default '{}'::jsonb,
 unique(method_id,method_version,symbol,suggested_date,side)
);
create index sector_swing_suggestions_date on public.sector_swing_suggestions(suggested_date desc,symbol,id);
alter table public.sector_swing_suggestions enable row level security;
revoke all on public.sector_swing_suggestions from public,anon,authenticated;
grant select on public.sector_swing_suggestions to authenticated;
grant select,insert on public.sector_swing_suggestions to service_role;
create policy sector_swing_suggestions_allowlist_read on public.sector_swing_suggestions
 for select to authenticated using ((select public.is_trading_research_web_user()));
comment on table public.sector_swing_suggestions is 'Tracker-only recorded signal snapshots. Retrospective matches use historical closing references, not executable fills. Read access follows MULtipLY allowlist; no client writes.';
