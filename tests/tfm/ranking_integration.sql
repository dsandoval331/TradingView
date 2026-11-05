-- Entire integration fixture is rolled back. Never persists synthetic ranks or XP.
begin;
create temp table tfm_rank_models (like public.tfm_rank_models including all);
create temp table tfm_rank_snapshots (like public.tfm_rank_snapshots including all);
create temp table tfm_rank_reviews (like public.tfm_rank_reviews including all);
create temp table tfm_rank_xp (like public.tfm_rank_xp including all);
create temp table tfm_runs (like public.tfm_runs including all);
create temp table tfm_setups (like public.tfm_setups including all);
create temp table tfm_outcomes (like public.tfm_outcomes including all);
create temp table work_envelopes (like public.work_envelopes including all);
insert into pg_temp.tfm_rank_models select * from public.tfm_rank_models;
insert into pg_temp.work_envelopes select * from public.work_envelopes where mwe_id='MWE-SECTOR-TFM-001';
insert into pg_temp.tfm_runs select * from public.tfm_runs where status='COMPLETE';
insert into pg_temp.tfm_setups select * from public.tfm_setups where friday='2026-10-30';
update pg_temp.tfm_setups set friday='2026-11-06',target_date='2026-11-09',origin='PROSPECTIVE',recorded_at='2026-11-07T13:15:00Z',
payload=jsonb_set(jsonb_set(payload,'{reference_bars,0,trade_date}','"2026-11-05"'),'{reference_bars,1,trade_date}','"2026-11-06"');
create or replace function pg_temp.test_process_rankings(p_run_id uuid) returns jsonb language plpgsql security invoker set search_path='' as $$
declare m pg_temp.tfm_rank_models%rowtype; w record; sc record; snap record; review jsonb; items jsonb; ranked jsonb; t date; mon date; scope_rows integer; all_ok boolean; published integer:=0; reviewed integer:=0;
begin
 perform pg_advisory_xact_lock(hashtext('tfm-ranking-v1'));
 if not exists(select 1 from pg_temp.tfm_runs where run_id=p_run_id and status='COMPLETE') then raise exception 'TFM_SCAN_NOT_COMPLETE'; end if;
 if not exists(select 1 from pg_temp.work_envelopes where mwe_id='MWE-SECTOR-TFM-001' and authority_ceiling='E1' and cost_policy_code='ZERO_INCREMENTAL_COST_FIRST') then raise exception 'TFM_AUTHORITY_MISSING'; end if;
 select * into strict m from pg_temp.tfm_rank_models where version='tfm-rank-v1';
 -- Complete baseline universe is required before a scope may freeze, even for nonqualifiers.
 for w in select distinct friday,target_date from pg_temp.tfm_setups where friday+3>=m.effective_monday and rule_version='tfm-bearish-v2' order by friday loop
 mon:=w.friday+3;t:=w.target_date;
 if timestamptz '2026-11-07 13:15:00+00'>=((w.friday+time '16:00') at time zone 'America/New_York') and timestamptz '2026-11-07 13:15:00+00'<((t+time '09:30') at time zone 'America/New_York') then
  for sc in select key,value from jsonb_each(m.config->'scopes') loop
   if exists(select 1 from pg_temp.tfm_rank_snapshots where model_version=m.version and scope=sc.key and monday=mon) then continue; end if;
   select count(*),jsonb_agg(to_jsonb(s) order by s.symbol),bool_and(s.origin='PROSPECTIVE' and r.status='COMPLETE' and coalesce((r.diagnostics->>'reference_corrections')::int,0)=0)
   into scope_rows,items,all_ok from pg_temp.tfm_setups s join pg_temp.tfm_runs r using(run_id)
   where s.rule_version='tfm-bearish-v2' and s.friday=w.friday and s.target_date=t and s.symbol in(select jsonb_array_elements_text(sc.value));
   if scope_rows<>jsonb_array_length(sc.value) or not coalesce(all_ok,false) then continue; end if;
   ranked:=public.tfm_score_candidates(items);
   insert into pg_temp.tfm_rank_snapshots(model_version,scope,monday,target_date,run_id,payload)
   values(m.version,sc.key,mon,t,p_run_id,jsonb_build_object('model_sha256',m.model_sha256,'config',m.config,'universe',sc.value,
   'universe_sha256',encode(sha256(convert_to(sc.value::text,'UTF8')),'hex'),'source_sha256',encode(sha256(convert_to(items::text,'UTF8')),'hex'),
   'baseline_n',scope_rows,'n',jsonb_array_length(ranked),'k',least(5,jsonb_array_length(ranked)),
   'complete',not exists(select 1 from jsonb_array_elements(ranked) x where x->>'status'<>'RANKED'),'candidates',ranked));published:=published+1;
  end loop;
 end if;
 end loop;
 for snap in select s.* from pg_temp.tfm_rank_snapshots s left join pg_temp.tfm_rank_reviews r using(snapshot_id)
 where r.snapshot_id is null and s.model_version=m.version and (s.payload->>'complete')::boolean
 and timestamptz '2026-11-07 13:15:00+00'>((s.target_date+time '16:00') at time zone 'America/New_York') loop
  -- Source corrections block final review, including corrections detected on a retry.
  if exists(select 1 from pg_temp.tfm_runs where run_id=p_run_id and
   (coalesce((diagnostics->>'reference_corrections')::int,0)>0 or coalesce((diagnostics->>'outcome_corrections')::int,0)>0)) then continue;end if;
  select coalesce(jsonb_agg(x||jsonb_build_object('outcome',o.payload,'result_sha256',o.result_sha256) order by (x->>'rank')::int),'[]'::jsonb) into items
  from jsonb_array_elements(snap.payload->'candidates') x left join pg_temp.tfm_outcomes o on o.setup_key=x->>'setup_key' and o.setup_sha256=x->>'setup_sha256'
  left join pg_temp.tfm_runs rr on rr.run_id=o.run_id
  where o.setup_key is null or rr.status='COMPLETE';
  review:=public.tfm_score_review(items);
  if (review->>'complete')::boolean and (review->>'n')::int=(snap.payload->>'n')::int then
   insert into pg_temp.tfm_rank_reviews(snapshot_id,payload) values(snap.snapshot_id,review);reviewed:=reviewed+1;
  end if;
 end loop;
 -- One event per week across ALL three pools; constrained kinds make the 30 XP cap structural.
 insert into pg_temp.tfm_rank_xp(monday,kind,evidence)
 select monday,'freeze',jsonb_build_object('snapshot_ids',jsonb_agg(snapshot_id),'model',m.version)
 from pg_temp.tfm_rank_snapshots where model_version=m.version group by monday
 having count(distinct scope)=3 and bool_and((payload->>'complete')::boolean) on conflict do nothing;
 insert into pg_temp.tfm_rank_xp(monday,kind,evidence)
 select s.monday,'review',jsonb_build_object('snapshot_ids',jsonb_agg(s.snapshot_id)) from pg_temp.tfm_rank_snapshots s
 join pg_temp.tfm_rank_reviews r using(snapshot_id) join pg_temp.tfm_rank_xp xp on xp.monday=s.monday and xp.kind='freeze'
 where s.model_version=m.version group by s.monday having count(distinct s.scope)=3 on conflict do nothing;
 insert into pg_temp.tfm_rank_xp(monday,kind,evidence)
 select monday,'integrity',evidence||jsonb_build_object('verified_run',p_run_id) from pg_temp.tfm_rank_xp where kind='review' on conflict do nothing;
 return jsonb_build_object('snapshots_added',published,'reviews_added',reviewed,'model',m.version);
end $$;
select pg_temp.test_process_rankings((select run_id from pg_temp.tfm_runs order by completed_at desc limit 1));
select pg_temp.test_process_rankings((select run_id from pg_temp.tfm_runs order by completed_at desc limit 1));
do $$ begin
 if (select count(*) from pg_temp.tfm_rank_snapshots)<>3 or (select sum(points) from pg_temp.tfm_rank_xp)<>10 then raise exception 'FREEZE_IDEMPOTENCE_FAILED';end if;
end $$;
create or replace function pg_temp.test_process_rankings(p_run_id uuid) returns jsonb language plpgsql security invoker set search_path='' as $$
declare m pg_temp.tfm_rank_models%rowtype; w record; sc record; snap record; review jsonb; items jsonb; ranked jsonb; t date; mon date; scope_rows integer; all_ok boolean; published integer:=0; reviewed integer:=0;
begin
 perform pg_advisory_xact_lock(hashtext('tfm-ranking-v1'));
 if not exists(select 1 from pg_temp.tfm_runs where run_id=p_run_id and status='COMPLETE') then raise exception 'TFM_SCAN_NOT_COMPLETE'; end if;
 if not exists(select 1 from pg_temp.work_envelopes where mwe_id='MWE-SECTOR-TFM-001' and authority_ceiling='E1' and cost_policy_code='ZERO_INCREMENTAL_COST_FIRST') then raise exception 'TFM_AUTHORITY_MISSING'; end if;
 select * into strict m from pg_temp.tfm_rank_models where version='tfm-rank-v1';
 -- Complete baseline universe is required before a scope may freeze, even for nonqualifiers.
 for w in select distinct friday,target_date from pg_temp.tfm_setups where friday+3>=m.effective_monday and rule_version='tfm-bearish-v2' order by friday loop
 mon:=w.friday+3;t:=w.target_date;
 if timestamptz '2026-11-10 13:15:00+00'>=((w.friday+time '16:00') at time zone 'America/New_York') and timestamptz '2026-11-10 13:15:00+00'<((t+time '09:30') at time zone 'America/New_York') then
  for sc in select key,value from jsonb_each(m.config->'scopes') loop
   if exists(select 1 from pg_temp.tfm_rank_snapshots where model_version=m.version and scope=sc.key and monday=mon) then continue; end if;
   select count(*),jsonb_agg(to_jsonb(s) order by s.symbol),bool_and(s.origin='PROSPECTIVE' and r.status='COMPLETE' and coalesce((r.diagnostics->>'reference_corrections')::int,0)=0)
   into scope_rows,items,all_ok from pg_temp.tfm_setups s join pg_temp.tfm_runs r using(run_id)
   where s.rule_version='tfm-bearish-v2' and s.friday=w.friday and s.target_date=t and s.symbol in(select jsonb_array_elements_text(sc.value));
   if scope_rows<>jsonb_array_length(sc.value) or not coalesce(all_ok,false) then continue; end if;
   ranked:=public.tfm_score_candidates(items);
   insert into pg_temp.tfm_rank_snapshots(model_version,scope,monday,target_date,run_id,payload)
   values(m.version,sc.key,mon,t,p_run_id,jsonb_build_object('model_sha256',m.model_sha256,'config',m.config,'universe',sc.value,
   'universe_sha256',encode(sha256(convert_to(sc.value::text,'UTF8')),'hex'),'source_sha256',encode(sha256(convert_to(items::text,'UTF8')),'hex'),
   'baseline_n',scope_rows,'n',jsonb_array_length(ranked),'k',least(5,jsonb_array_length(ranked)),
   'complete',not exists(select 1 from jsonb_array_elements(ranked) x where x->>'status'<>'RANKED'),'candidates',ranked));published:=published+1;
  end loop;
 end if;
 end loop;
 for snap in select s.* from pg_temp.tfm_rank_snapshots s left join pg_temp.tfm_rank_reviews r using(snapshot_id)
 where r.snapshot_id is null and s.model_version=m.version and (s.payload->>'complete')::boolean
 and timestamptz '2026-11-10 13:15:00+00'>((s.target_date+time '16:00') at time zone 'America/New_York') loop
  -- Source corrections block final review, including corrections detected on a retry.
  if exists(select 1 from pg_temp.tfm_runs where run_id=p_run_id and
   (coalesce((diagnostics->>'reference_corrections')::int,0)>0 or coalesce((diagnostics->>'outcome_corrections')::int,0)>0)) then continue;end if;
  select coalesce(jsonb_agg(x||jsonb_build_object('outcome',o.payload,'result_sha256',o.result_sha256) order by (x->>'rank')::int),'[]'::jsonb) into items
  from jsonb_array_elements(snap.payload->'candidates') x left join pg_temp.tfm_outcomes o on o.setup_key=x->>'setup_key' and o.setup_sha256=x->>'setup_sha256'
  left join pg_temp.tfm_runs rr on rr.run_id=o.run_id
  where o.setup_key is null or rr.status='COMPLETE';
  review:=public.tfm_score_review(items);
  if (review->>'complete')::boolean and (review->>'n')::int=(snap.payload->>'n')::int then
   insert into pg_temp.tfm_rank_reviews(snapshot_id,payload) values(snap.snapshot_id,review);reviewed:=reviewed+1;
  end if;
 end loop;
 -- One event per week across ALL three pools; constrained kinds make the 30 XP cap structural.
 insert into pg_temp.tfm_rank_xp(monday,kind,evidence)
 select monday,'freeze',jsonb_build_object('snapshot_ids',jsonb_agg(snapshot_id),'model',m.version)
 from pg_temp.tfm_rank_snapshots where model_version=m.version group by monday
 having count(distinct scope)=3 and bool_and((payload->>'complete')::boolean) on conflict do nothing;
 insert into pg_temp.tfm_rank_xp(monday,kind,evidence)
 select s.monday,'review',jsonb_build_object('snapshot_ids',jsonb_agg(s.snapshot_id)) from pg_temp.tfm_rank_snapshots s
 join pg_temp.tfm_rank_reviews r using(snapshot_id) join pg_temp.tfm_rank_xp xp on xp.monday=s.monday and xp.kind='freeze'
 where s.model_version=m.version group by s.monday having count(distinct s.scope)=3 on conflict do nothing;
 insert into pg_temp.tfm_rank_xp(monday,kind,evidence)
 select monday,'integrity',evidence||jsonb_build_object('verified_run',p_run_id) from pg_temp.tfm_rank_xp where kind='review' on conflict do nothing;
 return jsonb_build_object('snapshots_added',published,'reviews_added',reviewed,'model',m.version);
end $$;
select pg_temp.test_process_rankings((select run_id from pg_temp.tfm_runs order by completed_at desc limit 1));
do $$ begin if (select count(*) from pg_temp.tfm_rank_reviews)<>0 or (select sum(points) from pg_temp.tfm_rank_xp)<>10 then raise exception 'MISSING_OUTCOME_AWARD_FAILED';end if;end $$;
insert into pg_temp.tfm_outcomes select o.* from public.tfm_outcomes o join pg_temp.tfm_setups s using(setup_key);
select pg_temp.test_process_rankings((select run_id from pg_temp.tfm_runs order by completed_at desc limit 1));
select pg_temp.test_process_rankings((select run_id from pg_temp.tfm_runs order by completed_at desc limit 1));
do $$ begin if (select count(*) from pg_temp.tfm_rank_reviews)<>3 or (select sum(points) from pg_temp.tfm_rank_xp)<>25 then raise exception 'REVIEW_XP_IDEMPOTENCE_FAILED';end if;end $$;
create or replace function pg_temp.test_process_rankings(p_run_id uuid) returns jsonb language plpgsql security invoker set search_path='' as $$
declare m pg_temp.tfm_rank_models%rowtype; w record; sc record; snap record; review jsonb; items jsonb; ranked jsonb; t date; mon date; scope_rows integer; all_ok boolean; published integer:=0; reviewed integer:=0;
begin
 perform pg_advisory_xact_lock(hashtext('tfm-ranking-v1'));
 if not exists(select 1 from pg_temp.tfm_runs where run_id=p_run_id and status='COMPLETE') then raise exception 'TFM_SCAN_NOT_COMPLETE'; end if;
 if not exists(select 1 from pg_temp.work_envelopes where mwe_id='MWE-SECTOR-TFM-001' and authority_ceiling='E1' and cost_policy_code='ZERO_INCREMENTAL_COST_FIRST') then raise exception 'TFM_AUTHORITY_MISSING'; end if;
 select * into strict m from pg_temp.tfm_rank_models where version='tfm-rank-v1';
 -- Complete baseline universe is required before a scope may freeze, even for nonqualifiers.
 for w in select distinct friday,target_date from pg_temp.tfm_setups where friday+3>=m.effective_monday and rule_version='tfm-bearish-v2' order by friday loop
 mon:=w.friday+3;t:=w.target_date;
 if timestamptz '2026-11-17 13:15:00+00'>=((w.friday+time '16:00') at time zone 'America/New_York') and timestamptz '2026-11-17 13:15:00+00'<((t+time '09:30') at time zone 'America/New_York') then
  for sc in select key,value from jsonb_each(m.config->'scopes') loop
   if exists(select 1 from pg_temp.tfm_rank_snapshots where model_version=m.version and scope=sc.key and monday=mon) then continue; end if;
   select count(*),jsonb_agg(to_jsonb(s) order by s.symbol),bool_and(s.origin='PROSPECTIVE' and r.status='COMPLETE' and coalesce((r.diagnostics->>'reference_corrections')::int,0)=0)
   into scope_rows,items,all_ok from pg_temp.tfm_setups s join pg_temp.tfm_runs r using(run_id)
   where s.rule_version='tfm-bearish-v2' and s.friday=w.friday and s.target_date=t and s.symbol in(select jsonb_array_elements_text(sc.value));
   if scope_rows<>jsonb_array_length(sc.value) or not coalesce(all_ok,false) then continue; end if;
   ranked:=public.tfm_score_candidates(items);
   insert into pg_temp.tfm_rank_snapshots(model_version,scope,monday,target_date,run_id,payload)
   values(m.version,sc.key,mon,t,p_run_id,jsonb_build_object('model_sha256',m.model_sha256,'config',m.config,'universe',sc.value,
   'universe_sha256',encode(sha256(convert_to(sc.value::text,'UTF8')),'hex'),'source_sha256',encode(sha256(convert_to(items::text,'UTF8')),'hex'),
   'baseline_n',scope_rows,'n',jsonb_array_length(ranked),'k',least(5,jsonb_array_length(ranked)),
   'complete',not exists(select 1 from jsonb_array_elements(ranked) x where x->>'status'<>'RANKED'),'candidates',ranked));published:=published+1;
  end loop;
 end if;
 end loop;
 for snap in select s.* from pg_temp.tfm_rank_snapshots s left join pg_temp.tfm_rank_reviews r using(snapshot_id)
 where r.snapshot_id is null and s.model_version=m.version and (s.payload->>'complete')::boolean
 and timestamptz '2026-11-17 13:15:00+00'>((s.target_date+time '16:00') at time zone 'America/New_York') loop
  -- Source corrections block final review, including corrections detected on a retry.
  if exists(select 1 from pg_temp.tfm_runs where run_id=p_run_id and
   (coalesce((diagnostics->>'reference_corrections')::int,0)>0 or coalesce((diagnostics->>'outcome_corrections')::int,0)>0)) then continue;end if;
  select coalesce(jsonb_agg(x||jsonb_build_object('outcome',o.payload,'result_sha256',o.result_sha256) order by (x->>'rank')::int),'[]'::jsonb) into items
  from jsonb_array_elements(snap.payload->'candidates') x left join pg_temp.tfm_outcomes o on o.setup_key=x->>'setup_key' and o.setup_sha256=x->>'setup_sha256'
  left join pg_temp.tfm_runs rr on rr.run_id=o.run_id
  where o.setup_key is null or rr.status='COMPLETE';
  review:=public.tfm_score_review(items);
  if (review->>'complete')::boolean and (review->>'n')::int=(snap.payload->>'n')::int then
   insert into pg_temp.tfm_rank_reviews(snapshot_id,payload) values(snap.snapshot_id,review);reviewed:=reviewed+1;
  end if;
 end loop;
 -- One event per week across ALL three pools; constrained kinds make the 30 XP cap structural.
 insert into pg_temp.tfm_rank_xp(monday,kind,evidence)
 select monday,'freeze',jsonb_build_object('snapshot_ids',jsonb_agg(snapshot_id),'model',m.version)
 from pg_temp.tfm_rank_snapshots where model_version=m.version group by monday
 having count(distinct scope)=3 and bool_and((payload->>'complete')::boolean) on conflict do nothing;
 insert into pg_temp.tfm_rank_xp(monday,kind,evidence)
 select s.monday,'review',jsonb_build_object('snapshot_ids',jsonb_agg(s.snapshot_id)) from pg_temp.tfm_rank_snapshots s
 join pg_temp.tfm_rank_reviews r using(snapshot_id) join pg_temp.tfm_rank_xp xp on xp.monday=s.monday and xp.kind='freeze'
 where s.model_version=m.version group by s.monday having count(distinct s.scope)=3 on conflict do nothing;
 insert into pg_temp.tfm_rank_xp(monday,kind,evidence)
 select monday,'integrity',evidence||jsonb_build_object('verified_run',p_run_id) from pg_temp.tfm_rank_xp where kind='review' on conflict do nothing;
 return jsonb_build_object('snapshots_added',published,'reviews_added',reviewed,'model',m.version);
end $$;

-- A late start cannot reconstruct prospective ranks, even with complete historical outcomes.
insert into pg_temp.tfm_setups select encode(sha256(convert_to(setup_key||'-late','UTF8')),'hex'),rule_version,run_id,symbol,friday+7,target_date+7,cohort,qualifies,origin,setup_sha256,payload,recorded_at+interval '7 days' from pg_temp.tfm_setups;
select pg_temp.test_process_rankings((select run_id from pg_temp.tfm_runs order by completed_at desc limit 1));
do $$ begin if (select count(*) from pg_temp.tfm_rank_snapshots)<>3 or (select sum(points) from pg_temp.tfm_rank_xp)<>25 then raise exception 'HINDSIGHT_RANKING_FAILED';end if;end $$;
rollback;
select 'TFM full-pipeline freeze/review/XP/retry/late-start integration PASS (all fixtures rolled back)' as result;
