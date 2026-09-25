-- Operational Health v2 persistence.
-- Infrastructure observability only: no research-job mutation is performed here.

create table if not exists public.research_queue_health_snapshots (
    snapshot_id uuid primary key default gen_random_uuid(),
    observed_at timestamptz not null,
    status text not null check (status in ('healthy', 'attention')),
    alerts text[] not null default '{}',
    snapshot_json jsonb not null,
    source text not null default 'queue_operational_health_v2',
    source_execution_id text,
    created_at timestamptz not null default now(),
    unique (source, observed_at)
);

create index if not exists research_queue_health_snapshots_observed_at_idx
    on public.research_queue_health_snapshots (observed_at desc);

create table if not exists public.research_queue_health_incidents (
    incident_id uuid primary key default gen_random_uuid(),
    incident_key text not null unique,
    alert_code text not null,
    state text not null check (state in ('open', 'recovered')),
    first_observed_at timestamptz not null,
    last_observed_at timestamptz not null,
    recovered_at timestamptz,
    observation_count integer not null default 1 check (observation_count >= 1),
    last_snapshot_id uuid references public.research_queue_health_snapshots(snapshot_id),
    details_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check ((state = 'open' and recovered_at is null) or (state = 'recovered' and recovered_at is not null))
);

create index if not exists research_queue_health_incidents_state_idx
    on public.research_queue_health_incidents (state, last_observed_at desc);

alter table public.research_queue_health_snapshots enable row level security;
alter table public.research_queue_health_incidents enable row level security;

comment on table public.research_queue_health_snapshots is
    'Immutable operational-health observations. Infrastructure observability only.';
comment on table public.research_queue_health_incidents is
    'Deduplicated operational-health incident lifecycle. Does not authorize research-job mutation.';
