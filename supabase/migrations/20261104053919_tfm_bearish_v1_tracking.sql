-- MWE-SECTOR-TFM-001 | Tool: Sector Rotation Tracker
-- Append-only first verified setups/outcomes. Authenticated allowlist read only.
create table public.tfm_rules (
 version text primary key,
 rules_sha256 text not null check (rules_sha256 ~ '^[a-f0-9]{64}$'),
 contract jsonb not null,
 recorded_at timestamptz not null default now()
);
create table public.tfm_runs (
 run_id uuid primary key,
 rule_version text not null references public.tfm_rules(version),
 work_envelope_id uuid not null references public.work_envelopes(work_envelope_id),
 started_at timestamptz not null default now(),
 completed_at timestamptz,
 status text not null check (status in ('RUNNING','COMPLETE','FAILED')),
 git_sha text not null check (git_sha ~ '^[a-f0-9]{40}$'),
 external_run_id text,
 coverage jsonb not null default '{}',
 diagnostics jsonb not null default '{}'
);
create table public.tfm_setups (
 setup_key text primary key check (setup_key ~ '^[a-f0-9]{64}$'),
 rule_version text not null references public.tfm_rules(version),
 run_id uuid not null references public.tfm_runs(run_id),
 symbol text not null,
 friday date not null,
 target_date date not null,
 cohort text not null check (cohort in ('MONDAY','TUESDAY_HOLIDAY')),
 qualifies boolean not null,
 origin text not null check (origin in ('HISTORICAL','PROSPECTIVE')),
 setup_sha256 text not null check (setup_sha256 ~ '^[a-f0-9]{64}$'),
 payload jsonb not null,
 recorded_at timestamptz not null default now(),
 unique (rule_version,symbol,friday),
 check (extract(isodow from friday)=5),
 check (target_date=friday+case when cohort='MONDAY' then 3 else 4 end),
 check (origin='HISTORICAL' or (recorded_at>=((friday+time '13:00') at time zone 'America/New_York') and recorded_at<((target_date+time '09:30') at time zone 'America/New_York')))
);
create table public.tfm_outcomes (
 setup_key text primary key references public.tfm_setups(setup_key),
 run_id uuid not null references public.tfm_runs(run_id),
 setup_sha256 text not null,
 result_sha256 text not null check (result_sha256 ~ '^[a-f0-9]{64}$'),
 payload jsonb not null,
 recorded_at timestamptz not null default now()
);
create index tfm_setups_dates on public.tfm_setups(rule_version,friday desc,symbol);
create index tfm_setups_run on public.tfm_setups(run_id);
create index tfm_outcomes_run on public.tfm_outcomes(run_id);
create index tfm_runs_version on public.tfm_runs(rule_version,started_at desc);
alter table public.tfm_rules enable row level security;
alter table public.tfm_runs enable row level security;
alter table public.tfm_setups enable row level security;
alter table public.tfm_outcomes enable row level security;
revoke all on public.tfm_rules,public.tfm_runs,public.tfm_setups,public.tfm_outcomes from public,anon,authenticated,service_role;
grant select on public.tfm_rules,public.tfm_runs,public.tfm_setups,public.tfm_outcomes to authenticated;
grant select,insert on public.tfm_rules,public.tfm_runs,public.tfm_setups,public.tfm_outcomes to service_role;
grant update (status,completed_at,coverage,diagnostics) on public.tfm_runs to service_role;
create policy tfm_rules_read on public.tfm_rules for select to authenticated using ((select public.is_trading_research_web_user()));
create policy tfm_runs_read on public.tfm_runs for select to authenticated using ((select public.is_trading_research_web_user()));
create policy tfm_setups_read on public.tfm_setups for select to authenticated using ((select public.is_trading_research_web_user()) and exists(select 1 from public.tfm_runs r where r.run_id=tfm_setups.run_id and r.status='COMPLETE'));
create policy tfm_outcomes_read on public.tfm_outcomes for select to authenticated using ((select public.is_trading_research_web_user()) and exists(select 1 from public.tfm_runs r where r.run_id=tfm_outcomes.run_id and r.status='COMPLETE'));
comment on table public.tfm_setups is 'TFM bearish v1: first recorded frozen reference bars, inclusive unfiltered baseline; prospective versus historical origin immutable. Current membership survivorship bias disclosed.';
comment on table public.tfm_outcomes is 'First verified target-session outcomes. Descriptive excursions from target open, not simulated executed trades. Corrections detected by scanner and require review; never silently rewrite.';
-- Publication is one transaction: failed attempts expose no partial candidate batch.
create function public.tfm_publish_scan(p_run_id uuid,p_setups jsonb,p_outcomes jsonb,p_coverage jsonb,p_diagnostics jsonb)
returns void language plpgsql security invoker set search_path=public,pg_temp as $$
begin
 perform pg_advisory_xact_lock(hashtext('tfm-bearish-v1'));
 if not exists(select 1 from public.tfm_runs where run_id=p_run_id and status='RUNNING') then
  raise exception 'TFM_RUN_NOT_RUNNING';
 end if;
 insert into public.tfm_setups(setup_key,rule_version,run_id,symbol,friday,target_date,cohort,qualifies,origin,setup_sha256,payload)
 select x.setup_key,x.rule_version,p_run_id,x.symbol,x.friday,x.target_date,x.cohort,x.qualifies,x.origin,x.setup_sha256,x.payload
 from jsonb_to_recordset(p_setups) as x(setup_key text,rule_version text,symbol text,friday date,target_date date,cohort text,qualifies boolean,origin text,setup_sha256 text,payload jsonb);
 if exists(select 1 from jsonb_to_recordset(p_outcomes) as x(setup_key text,setup_sha256 text)
 left join public.tfm_setups s on s.setup_key=x.setup_key and s.setup_sha256=x.setup_sha256 where s.setup_key is null) then
  raise exception 'TFM_REFERENCE_MISMATCH';
 end if;
 insert into public.tfm_outcomes(setup_key,run_id,setup_sha256,result_sha256,payload)
 select x.setup_key,p_run_id,x.setup_sha256,x.result_sha256,x.payload
 from jsonb_to_recordset(p_outcomes) as x(setup_key text,setup_sha256 text,result_sha256 text,payload jsonb);
 update public.tfm_runs set status='COMPLETE',completed_at=now(),coverage=p_coverage,diagnostics=p_diagnostics where run_id=p_run_id;
end; $$;
revoke all on function public.tfm_publish_scan(uuid,jsonb,jsonb,jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.tfm_publish_scan(uuid,jsonb,jsonb,jsonb,jsonb) to service_role;
