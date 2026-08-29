-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Open Backlog / Tangents
--
-- PURPOSE:
--   Shows PM+PD tangents, deferred ideas, blockers, and promoted work that
--   has not yet been completed/rejected/cancelled.
-- ============================================================================

select
    pb.backlog_id,
    pb.priority,
    pb.status,
    pb.category,
    pb.title,
    pb.description,

    pb.origin_phase,
    pb.blocking_current_phase,
    pb.why_it_matters,
    pb.promoted_to_phase,

    pb.created_at,
    pb.updated_at,
    pb.resolved_at

from public.project_backlog pb
join public.strategies s
    on s.strategy_id = pb.strategy_id

where s.strategy_code = 'PMPD'
  and pb.status not in ('complete', 'rejected', 'cancelled')

order by
    pb.blocking_current_phase desc,
    pb.priority nulls last,
    pb.created_at;
