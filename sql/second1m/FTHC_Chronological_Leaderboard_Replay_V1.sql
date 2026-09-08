-- FTHC Chronological Leaderboard Replay V1
-- Implements frozen Replay Model V1:
--   * prior trading dates only
--   * BULL / BEAR separate
--   * clean outcomes only (FAVORABLE / ADVERSE)
--   * 90 calendar-day rolling window
--   * 5-event shrinkage prior
--   * point-in-time directional baseline
--   * same-day signals share the same pre-day leaderboard state
--   * Recent-5 descriptive only
--   * Established = 90D N >= 5
--   * leaderboard version LBV0
--
-- This script rebuilds:
--   leaderboard_snapshots
--   leaderboard_history
--   ticker_direction_stats
--
-- It does NOT alter signals, entry context, checkpoints, or outcomes.

begin;

-- ---------------------------------------------------------------------------
-- 0) Clear only derived leaderboard tables so replay is rerunnable.
-- ---------------------------------------------------------------------------
truncate table public.leaderboard_snapshots;
truncate table public.leaderboard_history;
truncate table public.ticker_direction_stats;

-- ---------------------------------------------------------------------------
-- 1) Build the replay universe.
--    We evaluate one pre-day leaderboard state for every historical signal date.
-- ---------------------------------------------------------------------------
drop table if exists tmp_replay_dates;
create temporary table tmp_replay_dates as
select distinct (signal_timestamp at time zone 'America/New_York')::date as replay_date
from public.signals
where data_source = 'historical_30m'
order by 1;

drop table if exists tmp_symbol_direction_universe;
create temporary table tmp_symbol_direction_universe as
select distinct symbol, direction
from public.signals
where data_source = 'historical_30m';

-- ---------------------------------------------------------------------------
-- 2) Point-in-time statistics for every date x symbol x direction.
--    Prior dates only: signal_date < replay_date.
-- ---------------------------------------------------------------------------
drop table if exists tmp_replay_stats;
create temporary table tmp_replay_stats as
with clean_events as (
    select
        s.symbol,
        s.direction,
        (s.signal_timestamp at time zone 'America/New_York')::date as signal_date,
        s.signal_timestamp,
        case when o.primary_outcome = 'FAVORABLE' then 1 else 0 end as win,
        case when o.primary_outcome = 'ADVERSE'   then 1 else 0 end as loss
    from public.signals s
    join public.signal_outcomes o
      on o.signal_id = s.id
    where s.data_source = 'historical_30m'
      and o.primary_outcome in ('FAVORABLE','ADVERSE')
),
direction_baseline as (
    select
        d.replay_date,
        u.direction,
        count(e.*) as dir_n,
        coalesce(sum(e.win),0) as dir_wins,
        case
            when count(e.*) = 0 then 0.5::numeric
            else sum(e.win)::numeric / count(e.*)::numeric
        end as baseline_ff
    from tmp_replay_dates d
    cross join (select distinct direction from tmp_symbol_direction_universe) u
    left join clean_events e
      on e.direction = u.direction
     and e.signal_date < d.replay_date
    group by d.replay_date, u.direction
),
base as (
    select
        d.replay_date,
        u.symbol,
        u.direction,
        db.baseline_ff,

        -- all prior history
        count(e.*) filter (
            where e.signal_date < d.replay_date
        ) as all_history_n,

        coalesce(sum(e.win) filter (
            where e.signal_date < d.replay_date
        ),0) as all_history_wins,

        -- prior 90 calendar days, excluding current replay date
        count(e.*) filter (
            where e.signal_date < d.replay_date
              and e.signal_date >= d.replay_date - interval '90 days'
        ) as n_90d,

        coalesce(sum(e.win) filter (
            where e.signal_date < d.replay_date
              and e.signal_date >= d.replay_date - interval '90 days'
        ),0) as wins_90d

    from tmp_replay_dates d
    cross join tmp_symbol_direction_universe u
    join direction_baseline db
      on db.replay_date = d.replay_date
     and db.direction = u.direction
    left join clean_events e
      on e.symbol = u.symbol
     and e.direction = u.direction
     and e.signal_date < d.replay_date
    group by d.replay_date, u.symbol, u.direction, db.baseline_ff
),
recent5 as (
    select
        b.replay_date,
        b.symbol,
        b.direction,
        count(r.*) as recent5_n,
        coalesce(sum(r.win),0) as recent5_wins
    from base b
    left join lateral (
        select e.win
        from clean_events e
        where e.symbol = b.symbol
          and e.direction = b.direction
          and e.signal_date < b.replay_date
        order by e.signal_timestamp desc
        limit 5
    ) r on true
    group by b.replay_date, b.symbol, b.direction
),
scored as (
    select
        b.replay_date,
        b.symbol,
        b.direction,
        b.baseline_ff,

        b.all_history_n,
        case
            when b.all_history_n > 0
            then b.all_history_wins::numeric / b.all_history_n::numeric
        end as all_history_ff_pct,

        b.n_90d,
        case
            when b.n_90d > 0
            then b.wins_90d::numeric / b.n_90d::numeric
        end as ff_pct_90d,

        -- 5-event shrinkage prior at point-in-time directional baseline
        (b.wins_90d::numeric + 5.0 * b.baseline_ff)
            / (b.n_90d::numeric + 5.0) as adjusted_score_90d,

        r.recent5_n,
        case
            when r.recent5_n > 0
            then r.recent5_wins::numeric / r.recent5_n::numeric
        end as recent5_ff_pct,

        case
            when b.n_90d = 0 then 'INSUFFICIENT'
            when b.n_90d between 1 and 2 then 'PROVISIONAL'
            when b.n_90d between 3 and 4 then 'DEVELOPING'
            else 'ESTABLISHED'
        end as confidence_status
    from base b
    join recent5 r
      on r.replay_date = b.replay_date
     and r.symbol = b.symbol
     and r.direction = b.direction
),
ranked as (
    select
        s.*,

        case when s.all_history_n > 0 then
            rank() over (
                partition by s.replay_date, s.direction,
                             case when s.all_history_n > 0 then 1 else 0 end
                order by
                    s.adjusted_score_90d desc,
                    s.n_90d desc,
                    s.all_history_n desc,
                    s.symbol asc
            )
        end as current_rank,

        case when s.n_90d >= 5 then
            rank() over (
                partition by s.replay_date, s.direction,
                             case when s.n_90d >= 5 then 1 else 0 end
                order by
                    s.adjusted_score_90d desc,
                    s.n_90d desc,
                    s.all_history_n desc,
                    s.symbol asc
            )
        end as established_rank_90d
    from scored s
),
with_prev as (
    select
        r.*,
        lag(r.current_rank) over (
            partition by r.symbol, r.direction
            order by r.replay_date
        ) as previous_rank
    from ranked r
)
select
    replay_date,
    symbol,
    direction,
    baseline_ff,
    all_history_n,
    all_history_ff_pct,
    n_90d,
    ff_pct_90d,
    adjusted_score_90d,
    recent5_n,
    recent5_ff_pct,
    confidence_status,
    current_rank,
    established_rank_90d,
    previous_rank,
    case
        when previous_rank is not null and current_rank is not null
        then previous_rank - current_rank
    end as rank_change
from with_prev;

create index on tmp_replay_stats(replay_date, symbol, direction);

-- ---------------------------------------------------------------------------
-- 3) Immutable pre-signal snapshots.
--    Every signal on the same date receives the same pre-day leaderboard state.
-- ---------------------------------------------------------------------------
insert into public.leaderboard_snapshots (
    signal_id,
    snapshot_timestamp,
    symbol,
    direction,
    rank_90d,
    established_rank_90d,
    n_90d,
    ff_pct_90d,
    adjusted_score_90d,
    all_history_n,
    all_history_ff_pct,
    recent5_n,
    recent5_ff_pct,
    confidence_status,
    previous_rank,
    rank_change,
    leaderboard_version
)
select
    s.id,
    s.signal_timestamp,
    s.symbol,
    s.direction,
    rs.current_rank,
    rs.established_rank_90d,
    rs.n_90d,
    rs.ff_pct_90d,
    rs.adjusted_score_90d,
    rs.all_history_n,
    rs.all_history_ff_pct,
    rs.recent5_n,
    rs.recent5_ff_pct,
    rs.confidence_status,
    rs.previous_rank,
    rs.rank_change,
    'LBV0'
from public.signals s
join tmp_replay_stats rs
  on rs.replay_date = (s.signal_timestamp at time zone 'America/New_York')::date
 and rs.symbol = s.symbol
 and rs.direction = s.direction
where s.data_source = 'historical_30m';

-- ---------------------------------------------------------------------------
-- 4) Historical leaderboard states, one row per replay-date x symbol x direction.
--    Store only rows with at least one prior clean resolved event.
-- ---------------------------------------------------------------------------
insert into public.leaderboard_history (
    snapshot_timestamp,
    symbol,
    direction,
    rank_90d,
    established_rank_90d,
    n_90d,
    ff_pct_90d,
    adjusted_score_90d,
    all_history_n,
    all_history_ff_pct,
    confidence_status,
    leaderboard_version
)
select
    replay_date::timestamp at time zone 'America/New_York',
    symbol,
    direction,
    current_rank,
    established_rank_90d,
    n_90d,
    ff_pct_90d,
    adjusted_score_90d,
    all_history_n,
    all_history_ff_pct,
    confidence_status,
    'LBV0'
from tmp_replay_stats
where all_history_n > 0;

-- ---------------------------------------------------------------------------
-- 5) Current ticker-direction stats after ALL historical outcomes are known.
--    This is current state, not a historical pre-signal snapshot.
-- ---------------------------------------------------------------------------
with bounds as (
    select
        max((signal_timestamp at time zone 'America/New_York')::date) as max_date
    from public.signals
    where data_source = 'historical_30m'
),
clean_events as (
    select
        s.symbol,
        s.direction,
        (s.signal_timestamp at time zone 'America/New_York')::date as signal_date,
        s.signal_timestamp,
        case when o.primary_outcome = 'FAVORABLE' then 1 else 0 end as win
    from public.signals s
    join public.signal_outcomes o on o.signal_id = s.id
    where s.data_source = 'historical_30m'
      and o.primary_outcome in ('FAVORABLE','ADVERSE')
),
dir_baseline as (
    select
        direction,
        case when count(*) = 0 then 0.5::numeric
             else sum(win)::numeric / count(*)::numeric
        end as baseline_ff
    from clean_events
    group by direction
),
agg as (
    select
        u.symbol,
        u.direction,
        b.max_date,
        db.baseline_ff,

        count(e.*) as all_history_n,
        coalesce(sum(e.win),0) as all_history_wins,

        count(e.*) filter (
            where e.signal_date >= b.max_date - interval '89 days'
              and e.signal_date <= b.max_date
        ) as n_90d,

        coalesce(sum(e.win) filter (
            where e.signal_date >= b.max_date - interval '89 days'
              and e.signal_date <= b.max_date
        ),0) as wins_90d,

        max(e.signal_timestamp) as last_signal_timestamp
    from tmp_symbol_direction_universe u
    cross join bounds b
    join dir_baseline db on db.direction = u.direction
    left join clean_events e
      on e.symbol = u.symbol
     and e.direction = u.direction
    group by u.symbol, u.direction, b.max_date, db.baseline_ff
),
recent5 as (
    select
        a.symbol,
        a.direction,
        count(r.*) as recent5_n,
        coalesce(sum(r.win),0) as recent5_wins
    from agg a
    left join lateral (
        select e.win
        from clean_events e
        where e.symbol = a.symbol
          and e.direction = a.direction
        order by e.signal_timestamp desc
        limit 5
    ) r on true
    group by a.symbol, a.direction
),
scored as (
    select
        a.symbol,
        a.direction,
        a.all_history_n,
        case when a.all_history_n > 0
             then a.all_history_wins::numeric / a.all_history_n::numeric
        end as all_history_ff_pct,
        a.n_90d,
        case when a.n_90d > 0
             then a.wins_90d::numeric / a.n_90d::numeric
        end as ff_pct_90d,
        (a.wins_90d::numeric + 5.0*a.baseline_ff)
            / (a.n_90d::numeric + 5.0) as adjusted_score_90d,
        r.recent5_n,
        case when r.recent5_n > 0
             then r.recent5_wins::numeric / r.recent5_n::numeric
        end as recent5_ff_pct,
        case
            when a.n_90d = 0 then 'INSUFFICIENT'
            when a.n_90d between 1 and 2 then 'PROVISIONAL'
            when a.n_90d between 3 and 4 then 'DEVELOPING'
            else 'ESTABLISHED'
        end as confidence_status,
        a.last_signal_timestamp
    from agg a
    join recent5 r
      on r.symbol = a.symbol
     and r.direction = a.direction
),
ranked as (
    select
        s.*,
        case when all_history_n > 0 then
            rank() over (
                partition by direction,
                             case when all_history_n > 0 then 1 else 0 end
                order by adjusted_score_90d desc,
                         n_90d desc,
                         all_history_n desc,
                         symbol asc
            )
        end as current_rank,
        case when n_90d >= 5 then
            rank() over (
                partition by direction,
                             case when n_90d >= 5 then 1 else 0 end
                order by adjusted_score_90d desc,
                         n_90d desc,
                         all_history_n desc,
                         symbol asc
            )
        end as established_rank_90d
    from scored s
)
insert into public.ticker_direction_stats (
    symbol,
    direction,
    n_90d,
    ff_pct_90d,
    adjusted_score_90d,
    all_history_n,
    all_history_ff_pct,
    recent5_n,
    recent5_ff_pct,
    current_rank,
    established_rank_90d,
    confidence_status,
    previous_rank,
    last_signal_timestamp,
    recalculated_at,
    leaderboard_version
)
select
    symbol,
    direction,
    n_90d,
    ff_pct_90d,
    adjusted_score_90d,
    all_history_n,
    all_history_ff_pct,
    recent5_n,
    recent5_ff_pct,
    current_rank,
    established_rank_90d,
    confidence_status,
    null,
    last_signal_timestamp,
    now(),
    'LBV0'
from ranked;

commit;

-- ---------------------------------------------------------------------------
-- Acceptance checks
-- ---------------------------------------------------------------------------

-- A) Every historical signal should have one immutable leaderboard snapshot.
select
    (select count(*) from public.leaderboard_snapshots) as leaderboard_snapshots,
    (select count(*) from public.signals where data_source='historical_30m') as historical_signals;

-- B) Current ticker-direction state should contain 224 rows (112 x 2).
select
    count(*) as ticker_direction_rows,
    count(*) filter (where direction='BULL') as bull_rows,
    count(*) filter (where direction='BEAR') as bear_rows
from public.ticker_direction_stats;

-- C) Snapshot rows must not contain future history:
--    all_history_n and n_90d can be zero, never negative.
select count(*) as invalid_snapshot_rows
from public.leaderboard_snapshots
where all_history_n < 0
   or n_90d < 0
   or recent5_n < 0
   or recent5_n > 5;

-- D) Current Top 10 BULL
select
    current_rank,
    symbol,
    n_90d,
    round((ff_pct_90d*100)::numeric,1) as ff_90d_pct,
    round((adjusted_score_90d*100)::numeric,1) as adjusted_score_pct,
    all_history_n,
    round((all_history_ff_pct*100)::numeric,1) as all_history_ff_pct,
    confidence_status
from public.ticker_direction_stats
where direction='BULL'
  and current_rank <= 10
order by current_rank;

-- E) Current Top 10 BEAR
select
    current_rank,
    symbol,
    n_90d,
    round((ff_pct_90d*100)::numeric,1) as ff_90d_pct,
    round((adjusted_score_90d*100)::numeric,1) as adjusted_score_pct,
    all_history_n,
    round((all_history_ff_pct*100)::numeric,1) as all_history_ff_pct,
    confidence_status
from public.ticker_direction_stats
where direction='BEAR'
  and current_rank <= 10
order by current_rank;
