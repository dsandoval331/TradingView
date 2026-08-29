-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Research Roadmap Summary
--
-- PURPOSE:
--   Summarizes the PM+PD factor roadmap by research family and status.
-- ============================================================================

select
    rf.priority as family_order,
    rf.family,

    count(*) as total_factors,

    count(*) filter (where rf.status = 'validated') as validated,
    count(*) filter (where rf.status = 'testing') as testing,
    count(*) filter (where rf.status = 'ready') as ready,
    count(*) filter (where rf.status = 'research_only') as research_only,
    count(*) filter (where rf.status = 'production_candidate') as production_candidate,
    count(*) filter (where rf.status = 'rejected') as rejected,
    count(*) filter (where rf.status = 'not_tested') as not_tested,

    count(*) filter (where rf.data_available is true) as data_available,
    count(*) filter (where rf.data_available is false) as data_not_available

from public.research_factors rf
join public.strategies s
    on s.strategy_id = rf.strategy_id

where s.strategy_code = 'PMPD'

group by
    rf.priority,
    rf.family

order by
    rf.priority,
    rf.family;
