create table if not exists public.research_queue_wakeup_events (
  event_id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.research_jobs(job_id) on delete cascade,
  event_type text not null default 'job_queued' check (event_type = 'job_queued'),
  created_at timestamptz not null default now(),
  dispatch_requested_at timestamptz,
  dispatch_acknowledged_at timestamptz,
  dispatch_request_id bigint,
  dispatch_status text not null default 'pending' check (dispatch_status in ('pending','requested','acknowledged','failed')),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  last_error text,
  unique (job_id, event_type)
);

create index if not exists research_queue_wakeup_events_pending_idx
  on public.research_queue_wakeup_events (dispatch_status, created_at)
  where dispatch_status in ('pending','failed');

alter table public.research_queue_wakeup_events enable row level security;

create or replace function public.trp_enqueue_research_queue_wakeup()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status = 'queued'
     and new.preferred_executor = 'github_actions'
     and coalesce(new.cloud_run_spend_approved, false) = false
     and length(coalesce(new.git_sha, '')) = 40
     and (tg_op = 'INSERT' or old.status is distinct from 'queued') then
    insert into public.research_queue_wakeup_events(job_id)
    values (new.job_id)
    on conflict (job_id, event_type) do nothing;
  end if;
  return new;
end;
$$;

drop trigger if exists research_jobs_queue_wakeup_outbox on public.research_jobs;
create trigger research_jobs_queue_wakeup_outbox
after insert or update of status on public.research_jobs
for each row execute function public.trp_enqueue_research_queue_wakeup();
