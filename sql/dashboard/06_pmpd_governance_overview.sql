-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Human-Readable Vertical Governance Dashboard
--
-- Recommended repo location:
--   sql/dashboard/07_pmpd_governance_vertical.sql
--
-- PURPOSE:
--   Human-readable "Where are we?" dashboard for PM+PD.
--   This is a READ-ONLY query and does not modify Supabase.
-- ============================================================================

with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
),

state as (
    select *
    from public.project_state
    where strategy_id = (select strategy_id from pmpd)
),

plan as (
    select
        count(*) as total,
        count(*) filter (where status = 'complete') as complete,
        count(*) filter (where status = 'active') as active,
        count(*) filter (where status = 'ready') as ready,
        count(*) filter (where status = 'blocked') as blocked,
        count(*) filter (where status = 'backlog') as backlog
    from public.program_phases
    where strategy_id = (select strategy_id from pmpd)
),

roadmap as (
    select
        count(*) as total,
        count(*) filter (where status = 'validated') as validated,
        count(*) filter (where status = 'testing') as testing,
        count(*) filter (where status = 'ready') as ready,
        count(*) filter (where status = 'research_only') as research_only,
        count(*) filter (where status = 'production_candidate') as production_candidate,
        count(*) filter (where status = 'rejected') as rejected,
        count(*) filter (where status = 'not_tested') as not_tested
    from public.research_factors
    where strategy_id = (select strategy_id from pmpd)
),

backlog as (
    select
        count(*) filter (
            where status not in ('complete','rejected','cancelled')
        ) as open_items,

        count(*) filter (
            where status not in ('complete','rejected','cancelled')
              and blocking_current_phase = true
        ) as blockers
    from public.project_backlog
    where strategy_id = (select strategy_id from pmpd)
)

select section, item, detail, status
from (

    select
        10 as sort_order,
        'CURRENT'::text as section,
        'Active Phase'::text as item,
        active_phase_code || ' — ' || active_phase_name as detail,
        'ACTIVE'::text as status
    from state

    union all

    select
        20,
        'NEXT',
        'Next Phase',
        next_phase_code || ' — ' || next_phase_name,
        'UPCOMING'
    from state

    union all

    select
        30,
        'BASELINE',
        'Model',
        baseline_model,
        baseline_status
    from state

    union all

    select
        40,
        'VALIDATION',
        'Forward Validation',
        baseline_model,
        forward_validation_status
    from state

    union all

    select
        50,
        'DATA',
        'Historical Dataset',
        'Historical Engine / Dataset',
        historical_dataset_status
    from state

    union all

    select
        60,
        'PLAN',
        'Total Phases',
        total::text,
        'INFO'
    from plan

    union all

    select
        61,
        'PLAN',
        'Completed',
        complete::text,
        'COMPLETE'
    from plan

    union all

    select
        62,
        'PLAN',
        'Active',
        active::text,
        'ACTIVE'
    from plan

    union all

    select
        63,
        'PLAN',
        'Ready',
        ready::text,
        'READY'
    from plan

    union all

    select
        64,
        'PLAN',
        'Backlog',
        backlog::text,
        'BACKLOG'
    from plan

    union all

    select
        65,
        'PLAN',
        'Blocked',
        blocked::text,
        case when blocked > 0 then 'BLOCKED' else 'CLEAR' end
    from plan

    union all

    select
        70,
        'ROADMAP',
        'Total Factors',
        total::text,
        'INFO'
    from roadmap

    union all

    select
        71,
        'ROADMAP',
        'Validated',
        validated::text,
        'VALIDATED'
    from roadmap

    union all

    select
        72,
        'ROADMAP',
        'Testing',
        testing::text,
        'TESTING'
    from roadmap

    union all

    select
        73,
        'ROADMAP',
        'Ready',
        ready::text,
        'READY'
    from roadmap

    union all

    select
        74,
        'ROADMAP',
        'Research Only',
        research_only::text,
        'RESEARCH'
    from roadmap

    union all

    select
        75,
        'ROADMAP',
        'Production Candidate',
        production_candidate::text,
        'CANDIDATE'
    from roadmap

    union all

    select
        76,
        'ROADMAP',
        'Rejected',
        rejected::text,
        'REJECTED'
    from roadmap

    union all

    select
        77,
        'ROADMAP',
        'Not Tested',
        not_tested::text,
        'NOT TESTED'
    from roadmap

    union all

    select
        80,
        'TANGENTS',
        'Open Backlog Items',
        open_items::text,
        case when open_items > 0 then 'REVIEW' else 'CLEAR' end
    from backlog

    union all

    select
        90,
        'BLOCKERS',
        'Blocking Items',
        blockers::text,
        case when blockers > 0 then 'BLOCKED' else 'CLEAR' end
    from backlog

    union all

    select
        100,
        'ROADMAP',
        'Version',
        roadmap_version,
        'AUTHORITATIVE'
    from state

    union all

    select
        110,
        'DECISION',
        'Last Decision',
        last_decision,
        'INFO'
    from state

) dashboard

order by sort_order;
