-- Thread: Tool: Sector Rotation Tracker | MWE-SECTOR-TFM-001
-- Approved 2026-11-04 CT. Append-only ranking pilot; primary rules unchanged.
create table public.tfm_rank_models (
 version text primary key, effective_monday date not null, approved_at timestamptz not null default now(),
 config jsonb not null, model_sha256 text not null check(model_sha256 ~ '^[a-f0-9]{64}$')
);
create table public.tfm_rank_snapshots (
 snapshot_id uuid primary key default gen_random_uuid(), model_version text not null references public.tfm_rank_models(version),
 scope text not null check(scope in ('sectors','tech','top50')), monday date not null, target_date date not null,
 frozen_at timestamptz not null default clock_timestamp(), run_id uuid not null references public.tfm_runs(run_id),
 payload jsonb not null, unique(model_version,scope,monday),
 check(frozen_at < ((target_date+time '09:30') at time zone 'America/New_York')),
 check(extract(isodow from monday)=1 and target_date in (monday,monday+1))
);
create table public.tfm_rank_reviews (
 snapshot_id uuid primary key references public.tfm_rank_snapshots(snapshot_id),
 recorded_at timestamptz not null default clock_timestamp(), payload jsonb not null
);
create table public.tfm_rank_xp (
 monday date not null, kind text not null check(kind in ('freeze','review','integrity','reflection')),
 points integer generated always as (case kind when 'freeze' then 10 when 'review' then 10 else 5 end) stored,
 recorded_at timestamptz not null default clock_timestamp(), evidence jsonb not null, primary key(monday,kind)
);
create table public.tfm_rank_reflections (
 monday date primary key, author_id uuid not null references auth.users(id), note text not null check(length(trim(note)) between 20 and 4000),
 recorded_at timestamptz not null default clock_timestamp()
);
-- No updates/deletes are granted: model, original scores, reviews and rewards remain frozen.
do $$ declare t text; begin
 foreach t in array array['tfm_rank_models','tfm_rank_snapshots','tfm_rank_reviews','tfm_rank_xp','tfm_rank_reflections'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('revoke all on public.%I from public,anon,authenticated,service_role',t);
 execute format('grant select on public.%I to authenticated',t);
 execute format('grant select,insert on public.%I to service_role',t);
 execute format('create policy %I on public.%I for select to authenticated using ((select public.is_trading_research_web_user()))',t||'_read',t);
 end loop;
end $$;
create index tfm_rank_snapshots_scope_date on public.tfm_rank_snapshots(scope,monday desc);

-- Pure scorer. Input rows carry immutable setup payloads/hashes; no outcome fields used.
create function public.tfm_score_candidates(p_rows jsonb) returns jsonb language sql immutable security invoker set search_path='' as $$
 with bars as (
 select s, s->'payload'->'reference_bars'->0 as th, s->'payload'->'reference_bars'->1 as fr
 from jsonb_array_elements(p_rows) s where (s->>'qualifies')::boolean
 ), valid as (
 select *, case when jsonb_array_length(s->'payload'->'reference_bars')=2
 and (fr->>'high')::numeric>(fr->>'low')::numeric and (fr->>'low')::numeric>0
 and (fr->>'close')::numeric between (fr->>'low')::numeric and (fr->>'high')::numeric
 and (fr->>'open')::numeric between (fr->>'low')::numeric and (fr->>'high')::numeric
 and (th->>'close')::numeric>0 and (th->>'high')::numeric>(fr->>'high')::numeric
 and th->>'trade_date'=((s->>'friday')::date-1)::text and fr->>'trade_date'=s->>'friday'
 and th->>'symbol'=s->>'symbol' and fr->>'symbol'=s->>'symbol'
 and th->>'response_sha256' ~ '^[a-f0-9]{64}$' and fr->>'response_sha256' ~ '^[a-f0-9]{64}$'
 and th->>'run_id' is not null and fr->>'run_id' is not null then true else false end as ok from bars
 ), components as (
 select *,case when ok then 70*(1-((fr->>'close')::numeric-(fr->>'low')::numeric)/((fr->>'high')::numeric-(fr->>'low')::numeric)) end as close_points,
 case when ok then case when (fr->>'close')::numeric<(fr->>'open')::numeric then 20 else 0 end end as red_points,
 case when ok then case when (fr->>'close')::numeric<(th->>'close')::numeric then 10 else 0 end end as below_points,
 case when ok then ((fr->>'close')::numeric-(fr->>'low')::numeric)/(fr->>'close')::numeric*100 end as distance_pct from valid
 ), scored as (select *,close_points+red_points+below_points as score from components),
 ordered as (select *,case when ok then row_number() over(order by ok desc,score desc nulls last,distance_pct,s->>'symbol') end as rank from scored)
 select coalesce(jsonb_agg(jsonb_build_object('setup_key',s->>'setup_key','symbol',s->>'symbol','setup_sha256',s->>'setup_sha256',
 'score',score,'rank',rank,'close_points',close_points,'red_points',red_points,'below_points',below_points,'distance_pct',distance_pct,
 'lower_third',case when ok then close_points>=70*2.0/3 end,'status',case when ok then 'RANKED' else 'UNRANKABLE' end,
 'reason',case when not ok then 'Invalid/missing Friday range, OHLC or source provenance' end,'reference_bars',s->'payload'->'reference_bars') order by ok desc,score desc nulls last,distance_pct,s->>'symbol'),'[]'::jsonb) from ordered;
$$;
-- Pure evaluator. An incomplete pool never receives final lift/NDCG or a winner substitution.
create function public.tfm_score_review(p_rows jsonb) returns jsonb language sql immutable security invoker set search_path='' as $$
 with a as (select x, (x->>'rank')::int r, x->'outcome' o from jsonb_array_elements(p_rows) x),
 b as (select *,o is not null and o<>'null'::jsonb as done,
 coalesce((o->>'hit')::boolean,false) as hit,
 not coalesce((o->>'hit')::boolean,false) and (o->>'mfe_pct')::numeric>=0.5
 and (o->>'mae_pct')::numeric>=0 and ((o->>'mae_pct')::numeric=0 or (o->>'mfe_pct')::numeric/nullif((o->>'mae_pct')::numeric,0)>=2) as alt from a),
 c as (select *,hit or coalesce(alt,false) win from b),
 z as (select count(*)::int n,least(5,count(*))::int k,count(*) filter(where done)::int completed,
 count(*) filter(where win)::int wins,count(*) filter(where r<=5 and done)::int top_done,
 count(*) filter(where r<=5 and win)::int top_wins,count(*) filter(where r<=5 and hit)::int top_hits,
 bool_and(r is not null) rankable,
 sum(case when r<=5 and win then 1/(ln((r+1)::numeric)/ln(2::numeric)) else 0 end) dcg,
 percentile_cont(0.5) within group(order by (o->>'mfe_pct')::float8) median_mfe,
 percentile_cont(0.5) within group(order by (o->>'mae_pct')::float8) median_mae,
 avg((o->>'mfe_pct')::numeric) mean_mfe,avg((o->>'mae_pct')::numeric) mean_mae,
 count(*) filter(where (o->>'gap_through')::boolean) gaps,
 coalesce(jsonb_agg(x||jsonb_build_object('classification',case when not done then 'PENDING' when hit then 'PATTERN' when alt then 'ALTERNATE' else 'NEITHER' end) order by r nulls last),'[]'::jsonb) instances from c),
 q as (select *,n=completed and coalesce(rankable,true) complete,
 (select sum(1/(ln((i+1)::numeric)/ln(2::numeric))) from generate_series(1,least(k,wins)) i) ideal from z)
 select jsonb_build_object('n',n,'k',k,'completed',completed,'complete',complete,'wins',wins,'top_done',top_done,'top_wins',top_wins,
 'top_rate',case when complete then 100.0*top_wins/nullif(k,0) end,'top_hit_rate',case when complete then 100.0*top_hits/nullif(k,0) end,
 'pool_rate',case when complete then 100.0*wins/nullif(n,0) end,
 'lift',case when complete then 100.0*top_wins/nullif(k,0)-100.0*wins/nullif(n,0) end,
 'ndcg',case when complete then 100*dcg/nullif(ideal,0) end,'median_mfe',median_mfe,'median_mae',median_mae,
 'mean_mfe',mean_mfe,'mean_mae',mean_mae,'gaps',gaps,'instances',instances,
 'groups',(select coalesce(jsonb_object_agg(g,jsonb_build_object('n',n,'wins',w,'rate',case when complete then 100.0*w/nullif(n,0) end)),'{}'::jsonb) from
 (select case when r<=5 then 'top' when r>(select n from z)-5 then 'bottom' else 'middle' end g,count(*) n,count(*) filter(where win) w from c group by 1) groups)) from q;
$$;
revoke all on function public.tfm_score_candidates(jsonb),public.tfm_score_review(jsonb) from public,anon,authenticated;
grant execute on function public.tfm_score_candidates(jsonb),public.tfm_score_review(jsonb) to service_role;

create function public.tfm_process_rankings(p_run_id uuid) returns jsonb language plpgsql security invoker set search_path='' as $$
declare m public.tfm_rank_models%rowtype; w record; sc record; snap record; review jsonb; items jsonb; ranked jsonb; t date; mon date; scope_rows integer; all_ok boolean; published integer:=0; reviewed integer:=0;
begin
 perform pg_advisory_xact_lock(hashtext('tfm-ranking-v1'));
 if not exists(select 1 from public.tfm_runs where run_id=p_run_id and status='COMPLETE') then raise exception 'TFM_SCAN_NOT_COMPLETE'; end if;
 if not exists(select 1 from public.work_envelopes where mwe_id='MWE-SECTOR-TFM-001' and authority_ceiling='E1' and cost_policy_code='ZERO_INCREMENTAL_COST_FIRST') then raise exception 'TFM_AUTHORITY_MISSING'; end if;
 select * into strict m from public.tfm_rank_models where version='tfm-rank-v1';
 -- Complete baseline universe is required before a scope may freeze, even for nonqualifiers.
 for w in select distinct friday,target_date from public.tfm_setups where friday+3>=m.effective_monday and rule_version='tfm-bearish-v2' order by friday loop
 mon:=w.friday+3;t:=w.target_date;
 if clock_timestamp()>=((w.friday+time '16:00') at time zone 'America/New_York') and clock_timestamp()<((t+time '09:30') at time zone 'America/New_York') then
  for sc in select key,value from jsonb_each(m.config->'scopes') loop
   if exists(select 1 from public.tfm_rank_snapshots where model_version=m.version and scope=sc.key and monday=mon) then continue; end if;
   select count(*),jsonb_agg(to_jsonb(s) order by s.symbol),bool_and(s.origin='PROSPECTIVE' and r.status='COMPLETE' and coalesce((r.diagnostics->>'reference_corrections')::int,0)=0)
   into scope_rows,items,all_ok from public.tfm_setups s join public.tfm_runs r using(run_id)
   where s.rule_version='tfm-bearish-v2' and s.friday=w.friday and s.target_date=t and s.symbol in(select jsonb_array_elements_text(sc.value));
   if scope_rows<>jsonb_array_length(sc.value) or not coalesce(all_ok,false) then continue; end if;
   ranked:=public.tfm_score_candidates(items);
   insert into public.tfm_rank_snapshots(model_version,scope,monday,target_date,run_id,payload)
   values(m.version,sc.key,mon,t,p_run_id,jsonb_build_object('model_sha256',m.model_sha256,'config',m.config,'universe',sc.value,
   'universe_sha256',encode(sha256(convert_to(sc.value::text,'UTF8')),'hex'),'source_sha256',encode(sha256(convert_to(items::text,'UTF8')),'hex'),
   'baseline_n',scope_rows,'n',jsonb_array_length(ranked),'k',least(5,jsonb_array_length(ranked)),
   'complete',not exists(select 1 from jsonb_array_elements(ranked) x where x->>'status'<>'RANKED'),'candidates',ranked));published:=published+1;
  end loop;
 end if;
 end loop;
 for snap in select s.* from public.tfm_rank_snapshots s left join public.tfm_rank_reviews r using(snapshot_id)
 where r.snapshot_id is null and s.model_version=m.version and (s.payload->>'complete')::boolean
 and clock_timestamp()>((s.target_date+time '16:00') at time zone 'America/New_York') loop
  -- Source corrections block final review, including corrections detected on a retry.
  if exists(select 1 from public.tfm_runs where run_id=p_run_id and
   (coalesce((diagnostics->>'reference_corrections')::int,0)>0 or coalesce((diagnostics->>'outcome_corrections')::int,0)>0)) then continue;end if;
  select coalesce(jsonb_agg(x||jsonb_build_object('outcome',o.payload,'result_sha256',o.result_sha256) order by (x->>'rank')::int),'[]'::jsonb) into items
  from jsonb_array_elements(snap.payload->'candidates') x left join public.tfm_outcomes o on o.setup_key=x->>'setup_key' and o.setup_sha256=x->>'setup_sha256'
  left join public.tfm_runs rr on rr.run_id=o.run_id
  where o.setup_key is null or rr.status='COMPLETE';
  review:=public.tfm_score_review(items);
  if (review->>'complete')::boolean and (review->>'n')::int=(snap.payload->>'n')::int then
   insert into public.tfm_rank_reviews(snapshot_id,payload) values(snap.snapshot_id,review);reviewed:=reviewed+1;
  end if;
 end loop;
 -- One event per week across ALL three pools; constrained kinds make the 30 XP cap structural.
 insert into public.tfm_rank_xp(monday,kind,evidence)
 select monday,'freeze',jsonb_build_object('snapshot_ids',jsonb_agg(snapshot_id),'model',m.version)
 from public.tfm_rank_snapshots where model_version=m.version group by monday
 having count(distinct scope)=3 and bool_and((payload->>'complete')::boolean) on conflict do nothing;
 insert into public.tfm_rank_xp(monday,kind,evidence)
 select s.monday,'review',jsonb_build_object('snapshot_ids',jsonb_agg(s.snapshot_id)) from public.tfm_rank_snapshots s
 join public.tfm_rank_reviews r using(snapshot_id) join public.tfm_rank_xp xp on xp.monday=s.monday and xp.kind='freeze'
 where s.model_version=m.version group by s.monday having count(distinct s.scope)=3 on conflict do nothing;
 insert into public.tfm_rank_xp(monday,kind,evidence)
 select monday,'integrity',evidence||jsonb_build_object('verified_run',p_run_id) from public.tfm_rank_xp where kind='review' on conflict do nothing;
 return jsonb_build_object('snapshots_added',published,'reviews_added',reviewed,'model',m.version);
end $$;
revoke all on function public.tfm_process_rankings(uuid) from public,anon,authenticated;
grant execute on function public.tfm_process_rankings(uuid) to service_role;
-- This bounded authenticated write must bypass direct-write denial to atomically award exactly 5 XP.
create function public.tfm_save_reflection(p_monday date,p_note text) returns void language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null or not public.is_trading_research_web_user() then raise exception 'TFM_ACCESS_DENIED';end if;
 if length(trim(p_note)) not between 20 and 4000 then raise exception 'TFM_NOTE_LENGTH_20_4000';end if;
 perform pg_advisory_xact_lock(hashtext('tfm-ranking-v1'));
 if not exists(select 1 from public.tfm_rank_xp where monday=p_monday and kind='review') then raise exception 'TFM_VERIFIED_REVIEW_REQUIRED';end if;
 insert into public.tfm_rank_reflections(monday,author_id,note) values(p_monday,auth.uid(),trim(p_note)) on conflict do nothing;
 insert into public.tfm_rank_xp(monday,kind,evidence) select p_monday,'reflection',jsonb_build_object('author_id',author_id,'saved_at',recorded_at)
 from public.tfm_rank_reflections where monday=p_monday on conflict do nothing;
end $$;
revoke all on function public.tfm_save_reflection(date,text) from public,anon,authenticated,service_role;
grant execute on function public.tfm_save_reflection(date,text) to authenticated;

insert into public.tfm_rank_models(version,effective_monday,config,model_sha256) values('tfm-rank-v1','2026-11-09','{"effective_monday":"2026-11-09","min_mfe_pct":0.5,"min_ratio":2,"scopes":{"sectors":["XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY"],"tech":["AAPL","AMD","AMZN","ANET","AVGO","CSCO","DELL","GOOGL","HPE","HPQ","IGV","META","MRVL","MSFT","MU","NVDA","ORCL","PLTR","STX","TSM","VRT","WDC"],"top50":["AAPL","ABBV","AMAT","AMD","AMZN","AVGO","BAC","BRK.B","CAT","COST","CSCO","CVX","GE","GEV","GOOG","GOOGL","GS","HD","IBM","INTC","JNJ","JPM","KLAC","KO","LIN","LLY","LRCX","MA","MCD","META","MRK","MS","MSFT","MU","NFLX","NVDA","ORCL","PEP","PG","PLTR","PM","QCOM","SNDK","TSLA","TXN","UNH","V","VZ","WFC","WMT","XOM"]},"source_rule":"tfm-bearish-v2","spec":"libfile_7757730a1c908191a4b5838df1510418","top_k":5,"weekly_xp_cap":30,"weights":[70,20,10]}'::jsonb,'2829771d0624e4ba5c80b59e133b43c431e5e90ae363a6e45e8d46e5ea704368');
