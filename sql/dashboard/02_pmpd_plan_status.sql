-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Full Program Plan Status
--
-- PURPOSE:
--   Shows every PM+PD program phase in roadmap order with current status.
-- ============================================================================

select
    pp.sequence_order,
    pp.phase_code,
    pp.phase_name,
    pp.status,
    pp.objective,
    pp.started_at,
    pp.completed_at,
    pp.next_phase_code,
    pp.exit_criteria

from public.program_phases pp
join public.strategies s
    on s.strategy_id = pp.strategy_id

where s.strategy_code = 'PMPD'

order by pp.sequence_order;
