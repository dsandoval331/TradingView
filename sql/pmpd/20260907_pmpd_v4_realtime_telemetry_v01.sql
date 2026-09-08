-- PM+PD V4 Real-Time Telemetry v0.1
-- Additive migration: reuses existing webhook_events + PMPD research tables.

begin;

-- 1) Immutable/deduplicated indicator settings snapshots.
create table if not exists public.indicator_settings_snapshots (
    settings_snapshot_id uuid primary key default gen_random_uuid(),
    strategy_id uuid null references public.strategies(strategy_id),
    indicator_family text not null,
    indicator_version text not null,
    schema_version text not null default 'RT_TELEMETRY_V0_1',
    settings_hash text not null,
    settings_json jsonb not null,
    created_at timestamptz not null default now(),
    unique (indicator_family, indicator_version, settings_hash)
);

alter table public.indicator_settings_snapshots enable row level security;
comment on table public.indicator_settings_snapshots is
'Immutable deduplicated indicator configuration snapshots used to reproduce realtime telemetry signal state.';

create index if not exists idx_indicator_settings_snapshots_strategy
    on public.indicator_settings_snapshots(strategy_id, indicator_family, indicator_version);

-- 2) Extend the existing raw webhook ledger for realtime telemetry observability.
alter table public.webhook_events
    add column if not exists strategy_id uuid null references public.strategies(strategy_id),
    add column if not exists indicator_family text null,
    add column if not exists indicator_version text null,
    add column if not exists payload_hash text null,
    add column if not exists semantic_event_key text null,
    add column if not exists validation_status text null,
    add column if not exists duplicate_status text null,
    add column if not exists pine_event_time timestamptz null,
    add column if not exists validation_completed_at timestamptz null,
    add column if not exists persisted_at timestamptz null,
    add column if not exists receiver_version text null,
    add column if not exists pine_to_receiver_ms bigint null,
    add column if not exists receiver_to_persist_ms bigint null,
    add column if not exists total_ingestion_ms bigint null;

-- Expand event-type whitelist without removing existing supported events.
alter table public.webhook_events
    drop constraint if exists webhook_events_event_type_check;

alter table public.webhook_events
    add constraint webhook_events_event_type_check check (
        event_type = any (array[
            'SIGNAL_CREATED'::text,
            'CP1_UPDATE'::text,
            'CP2_UPDATE'::text,
            'CP3_UPDATE'::text,
            'CP5_UPDATE'::text,
            'CP10_UPDATE'::text,
            'OUTCOME_RESOLVED'::text,
            'SESSION_FINAL'::text,
            'OSI_SIGNAL'::text,
            'OSI_CHECKPOINT'::text,
            'OSI_OUTCOME'::text,
            'PMPD_SIGNAL_CONFIRMED'::text
        ])
    );

alter table public.webhook_events
    drop constraint if exists webhook_events_validation_status_check;
alter table public.webhook_events
    add constraint webhook_events_validation_status_check check (
        validation_status is null or validation_status = any (array['VALID'::text,'INVALID'::text])
    );

alter table public.webhook_events
    drop constraint if exists webhook_events_duplicate_status_check;
alter table public.webhook_events
    add constraint webhook_events_duplicate_status_check check (
        duplicate_status is null or duplicate_status = any (array['UNIQUE'::text,'EXACT_DUPLICATE'::text,'SEMANTIC_DUPLICATE'::text])
    );

create index if not exists idx_webhook_events_strategy_received
    on public.webhook_events(strategy_id, received_at desc);
create index if not exists idx_webhook_events_indicator_received
    on public.webhook_events(indicator_family, indicator_version, received_at desc);
create index if not exists idx_webhook_events_semantic_event_key
    on public.webhook_events(semantic_event_key)
    where semantic_event_key is not null;
create index if not exists idx_webhook_events_payload_hash
    on public.webhook_events(payload_hash)
    where payload_hash is not null;

comment on column public.webhook_events.payload_hash is
'SHA-256 or equivalent hash of the exact inbound request body; used for exact-duplicate detection.';
comment on column public.webhook_events.semantic_event_key is
'Normalized identity of the underlying market event; used for semantic duplicate detection.';

-- 3) Link PMPD signals to their inbound webhook and exact settings snapshot.
alter table public.pm_pd_signals
    add column if not exists webhook_event_id bigint null references public.webhook_events(id),
    add column if not exists settings_snapshot_id uuid null references public.indicator_settings_snapshots(settings_snapshot_id),
    add column if not exists exchange text null,
    add column if not exists chart_timeframe text null,
    add column if not exists bar_open_time timestamptz null,
    add column if not exists bar_close_time timestamptz null,
    add column if not exists bar_state text null;

alter table public.pm_pd_signals
    drop constraint if exists pm_pd_signals_bar_state_check;
alter table public.pm_pd_signals
    add constraint pm_pd_signals_bar_state_check check (
        bar_state is null or bar_state = any (array['DEVELOPING'::text,'CONFIRMED'::text,'POST_CLOSE'::text])
    );

create unique index if not exists uq_pm_pd_signals_webhook_event_id
    on public.pm_pd_signals(webhook_event_id)
    where webhook_event_id is not null;
create index if not exists idx_pm_pd_signals_settings_snapshot
    on public.pm_pd_signals(settings_snapshot_id)
    where settings_snapshot_id is not null;
create index if not exists idx_pm_pd_signals_symbol_signal_timestamp
    on public.pm_pd_signals(symbol, signal_timestamp desc);

comment on column public.pm_pd_signals.webhook_event_id is
'Inbound webhook ledger row that produced this PMPD signal. Null for historical/reconstructed rows.';
comment on column public.pm_pd_signals.settings_snapshot_id is
'Exact immutable V4 settings snapshot active when this signal was emitted.';

-- 4) Register a dedicated realtime telemetry dataset for PMPD V4.
insert into public.datasets (
    strategy_id,
    dataset_key,
    dataset_name,
    dataset_version,
    description,
    source,
    source_detail,
    canonical_intraday_tf,
    timezone,
    baseline_model_version,
    processing_code_version,
    is_frozen,
    metadata_json
)
select
    s.strategy_id,
    'PMPD_V4_REALTIME_TELEMETRY_V01',
    'PM+PD V4 Real-Time Telemetry',
    '0.1',
    'Prospective TradingView webhook telemetry for the Real-Time Trade Advisor infrastructure POC. Advisory/AI outputs intentionally excluded.',
    'tradingview_webhook',
    'TradingView Pine PM+PD V4 confirmed-signal telemetry',
    '5m',
    'America/New_York',
    'V4',
    'RT_TELEMETRY_V0_1',
    false,
    jsonb_build_object(
        'research_platform_first', true,
        'advisor_enabled', false,
        'automatic_execution', false,
        'initial_event_type', 'PMPD_SIGNAL_CONFIRMED'
    )
from public.strategies s
where s.strategy_code = 'PMPD'
  and not exists (
      select 1 from public.datasets d
      where d.dataset_key = 'PMPD_V4_REALTIME_TELEMETRY_V01'
  );

commit;
