-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Full Research Factor Roadmap
--
-- PURPOSE:
--   Shows all PM+PD research factors and their current research status.
-- ============================================================================

select
    rf.priority,
    rf.factor_code,
    rf.family,
    rf.factor_name,
    rf.description,

    rf.status,
    rf.timing_type,
    rf.data_type,
    rf.data_available,
    rf.implementation_status,

    rf.tested_n,
    rf.tested_symbols,

    rf.finding,
    rf.predictive_strength,
    rf.temporal_robustness,
    rf.production_status,

    rf.dependencies,
    rf.roadmap_version,
    rf.updated_at

from public.research_factors rf
join public.strategies s
    on s.strategy_id = rf.strategy_id

where s.strategy_code = 'PMPD'

order by
    rf.priority,
    rf.factor_code;
