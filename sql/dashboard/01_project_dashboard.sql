-- ============================================================================
-- TRADING RESEARCH PLATFORM
-- Human-Readable Vertical Project Dashboard
--
-- Recommended repo location:
--   sql/dashboard/01_project_dashboard.sql
--
-- PURPOSE:
--   Human-readable status across all registered strategies/projects.
--   READ ONLY.
-- ============================================================================

with states as (
    select
        s.strategy_code,
        s.strategy_name,
        s.strategy_type,
        s.status as strategy_status,
        ps.active_phase_code,
        ps.active_phase_name,
        ps.next_phase_code,
        ps.next_phase_name,
        ps.blocker_count,
        ps.baseline_model,
        ps.baseline_status,
        ps.forward_validation_status,
        ps.historical_dataset_status,
        ps.active_tangent_count,
        ps.roadmap_version,
        ps.last_decision,
        ps.updated_at
    from public.strategies s
    left join public.project_state ps
        on ps.strategy_id = s.strategy_id
)

select
    strategy_code,
    section,
    item,
    detail,
    status
from (
    select
        strategy_code,
        10 as sort_order,
        'PROJECT'::text as section,
        'Strategy Name'::text as item,
        strategy_name::text as detail,
        strategy_status::text as status
    from states

    union all

    select
        strategy_code,
        20,
        'CURRENT',
        'Active Phase',
        coalesce(active_phase_code || ' — ' || active_phase_name, 'No active phase'),
        case when active_phase_code is null then 'NONE' else 'ACTIVE' end
    from states

    union all

    select
        strategy_code,
        30,
        'NEXT',
        'Next Phase',
        coalesce(next_phase_code || ' — ' || next_phase_name, 'No next phase'),
        case when next_phase_code is null then 'NONE' else 'UPCOMING' end
    from states

    union all

    select
        strategy_code,
        40,
        'BASELINE',
        'Model',
        coalesce(baseline_model, 'Not set'),
        coalesce(baseline_status, 'Not set')
    from states

    union all

    select
        strategy_code,
        50,
        'VALIDATION',
        'Forward Validation',
        coalesce(baseline_model, strategy_code),
        coalesce(forward_validation_status, 'Not set')
    from states

    union all

    select
        strategy_code,
        60,
        'DATA',
        'Historical Dataset',
        'Historical Dataset / Engine',
        coalesce(historical_dataset_status, 'Not set')
    from states

    union all

    select
        strategy_code,
        70,
        'TANGENTS',
        'Open / Active Tangents',
        coalesce(active_tangent_count, 0)::text,
        case when coalesce(active_tangent_count, 0) > 0 then 'REVIEW' else 'CLEAR' end
    from states

    union all

    select
        strategy_code,
        80,
        'BLOCKERS',
        'Blocking Items',
        coalesce(blocker_count, 0)::text,
        case when coalesce(blocker_count, 0) > 0 then 'BLOCKED' else 'CLEAR' end
    from states

    union all

    select
        strategy_code,
        90,
        'ROADMAP',
        'Version',
        coalesce(roadmap_version, 'Not set'),
        case when roadmap_version is null then 'NOT SET' else 'AUTHORITATIVE' end
    from states

    union all

    select
        strategy_code,
        100,
        'DECISION',
        'Last Decision',
        coalesce(last_decision, 'No decision recorded'),
        'INFO'
    from states
) dashboard
order by
    case when strategy_code = 'PLATFORM' then 0 else 1 end,
    strategy_code,
    sort_order;
