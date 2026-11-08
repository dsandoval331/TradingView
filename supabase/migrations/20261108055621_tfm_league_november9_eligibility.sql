alter table public.tfm_league_matches
 drop constraint tfm_league_matches_monday_check,
 add constraint tfm_league_matches_monday_check check (monday >= date '2026-11-09');

create or replace function public.tfm_process_league() returns void
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
 where s.model_version='tfm-rank-v1' and s.monday>=date '2026-11-09'
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


