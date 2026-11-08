create table public.tfm_league_matches (
 champion_id uuid primary key references public.tfm_rank_snapshots(snapshot_id),
 scope text not null check (scope in ('sectors','tech','top50')),
 monday date not null check (monday >= date '2026-11-16'),
 target_date date not null,
 frozen_at timestamptz not null default clock_timestamp(),
 version text not null default 'tfm-room-to-target-v1' check (version='tfm-room-to-target-v1'),
 picks jsonb not null,
 check (frozen_at < ((target_date+time '09:30') at time zone 'America/New_York'))
);
create table public.tfm_league_results (
 champion_id uuid primary key references public.tfm_league_matches(champion_id),
 recorded_at timestamptz not null default clock_timestamp(),
 payload jsonb not null
);
alter table public.tfm_league_matches enable row level security;
alter table public.tfm_league_results enable row level security;
revoke all on public.tfm_league_matches,public.tfm_league_results from public,anon,authenticated,service_role;
grant select on public.tfm_league_matches,public.tfm_league_results to authenticated,service_role;
grant insert on public.tfm_league_matches,public.tfm_league_results to service_role;
create policy tfm_league_matches_read on public.tfm_league_matches for select to authenticated using ((select public.is_trading_research_web_user()));
create policy tfm_league_results_read on public.tfm_league_results for select to authenticated using ((select public.is_trading_research_web_user()));

create function public.tfm_league_score(p_picks jsonb,p_review jsonb) returns jsonb
language sql immutable security invoker set search_path='' as $$
with entries as (
 select x->>'setup_key' as key,x->>'symbol' as symbol,(x->>'rank')::int <= 5 as champion,
 (x->>'challenger_rank')::int <= 5 as challenger,
 (x->'reference_bars'->1->>'low')::numeric as target,
 (y->'outcome'->'target_bar'->>'open')::numeric as opening,
 (y->'outcome'->'target_bar'->>'low')::numeric as low,
 (y->'outcome'->'target_bar'->>'high')::numeric as high,
 (y->'outcome'->'target_bar'->>'close')::numeric as closing,
 (y->'outcome'->>'hit')::boolean as hit
 from jsonb_array_elements(p_picks) x
 left join jsonb_array_elements(p_review->'instances') y on y->>'setup_key'=x->>'setup_key'
 where (x->>'rank')::int <=5 or (x->>'challenger_rank')::int <=5
), levels as (
 select *, (opening-target)/nullif(opening,0)*100 as gain,
 case when opening is null or opening<=0 or target is null or target<=0
 or low is null or high is null or closing is null or hit is null
 or low<=0 or low>least(opening,closing) or high<greatest(opening,closing) then 'MISSING'
 when opening<=target then 'SKIP'
 when low<=target and high>=opening*1.0075 then 'AMBIGUOUS'
 when high>=opening*1.0075 then 'STOP'
 when low<=target then 'TARGET'
 else 'CLOSE' end as exit
 from entries
), bounds as (
 select *,case exit when 'SKIP' then 0 when 'AMBIGUOUS' then -.75 when 'STOP' then -.75
 when 'TARGET' then gain when 'CLOSE' then (opening-closing)/opening*100 end as lo,
 case exit when 'SKIP' then 0 when 'AMBIGUOUS' then gain when 'STOP' then -.75
 when 'TARGET' then gain when 'CLOSE' then (opening-closing)/opening*100 end as hi
 from levels
), totals as (
 select count(*) filter(where champion) as k,
 count(*) filter(where exit='MISSING') as missing,
 count(*) filter(where exit='AMBIGUOUS') as ambiguous,
 avg(lo) filter(where champion) as champion_lo,avg(hi) filter(where champion) as champion_hi,
 avg(lo) filter(where challenger) as challenger_lo,avg(hi) filter(where challenger) as challenger_hi,
 count(*) filter(where champion and hit) as champion_hits,
 count(*) filter(where challenger and hit) as challenger_hits,
 sum(case when champion and challenger then 0 when challenger then lo else -hi end) as diff_lo,
 sum(case when champion and challenger then 0 when challenger then hi else -lo end) as diff_hi,
 coalesce(jsonb_agg(to_jsonb(bounds) order by symbol),'[]'::jsonb) as trades
 from bounds
)
select jsonb_build_object('k',k,'missing',missing,'ambiguous',ambiguous,
 'champion_lo',champion_lo,'champion_hi',champion_hi,'challenger_lo',challenger_lo,'challenger_hi',challenger_hi,
 'champion_hits',champion_hits,'challenger_hits',challenger_hits,
 'winner',case when k=0 then 'NO_PICKS' when missing>0 then 'PENDING'
 when diff_lo>0 then 'CHALLENGER' when diff_hi<0 then 'CHAMPION'
 when diff_lo=0 and diff_hi=0 then 'TIE' else 'PENDING' end,'trades',trades)
from totals;
$$;

create function public.tfm_process_league() returns void
language plpgsql security invoker set search_path='' as $$
begin
 perform pg_advisory_xact_lock(hashtext('tfm-league-v1'));
 insert into public.tfm_league_matches(champion_id,scope,monday,target_date,picks)
 select s.snapshot_id,s.scope,s.monday,s.target_date,p.picks
 from public.tfm_rank_snapshots s
 cross join lateral (
  select coalesce(jsonb_agg(x||jsonb_build_object('challenger_rank',rn,'room_to_stop',(x->>'distance_pct')::numeric/.75) order by rn),'[]'::jsonb) as picks
  from (
   select x,row_number() over(order by (x->>'distance_pct')::numeric desc,(x->>'rank')::int) rn
   from jsonb_array_elements(s.payload->'candidates') x
  ) ranked
 ) p
 where s.model_version='tfm-rank-v1' and s.monday>=date '2026-11-16'
 and (s.payload->>'complete')::boolean
 and statement_timestamp()<((s.target_date+time '09:30') at time zone 'America/New_York')
 on conflict do nothing;

 insert into public.tfm_league_results(champion_id,payload)
 select m.champion_id,public.tfm_league_score(m.picks,r.payload)
 from public.tfm_league_matches m join public.tfm_rank_reviews r on r.snapshot_id=m.champion_id
 where not exists(select 1 from public.tfm_league_results a where a.champion_id=m.champion_id)
 on conflict do nothing;
end;
$$;
revoke all on function public.tfm_process_league(),public.tfm_league_score(jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.tfm_process_league(),public.tfm_league_score(jsonb,jsonb) to service_role;

-- Validate simulated exit order and paired comparison without publishing fixtures.
do $$
declare picks jsonb; review jsonb; result jsonb;
begin
 picks := '[{"setup_key":"a","rank":1,"challenger_rank":1,"reference_bars":[{},{"low":99}]}]';
 review := '{"instances":[{"setup_key":"a","outcome":{"hit":true,"target_bar":{"open":100,"low":98,"high":101,"close":100}}}]}';
 result := public.tfm_league_score(picks,review);
 if result->>'winner'<>'TIE' or (result->>'champion_lo')::numeric<>-.75
 or (result->>'champion_hi')::numeric<>1 or (result->>'ambiguous')::int<>1 then
  raise exception 'League fixture failed: common ambiguous trade';
 end if;
 review := jsonb_set(review,'{instances,0,outcome,target_bar,open}','99');
 result := public.tfm_league_score(picks,review);
 if result->>'winner'<>'TIE' or (result->>'champion_lo')::numeric<>0 then
  raise exception 'League fixture failed: gap skip';
 end if;
 result := public.tfm_league_score(picks,'{"instances":[]}');
 if result->>'winner'<>'PENDING' or (result->>'missing')::int<>1 then
  raise exception 'League fixture failed: missing price';
 end if;
end;
$$;
