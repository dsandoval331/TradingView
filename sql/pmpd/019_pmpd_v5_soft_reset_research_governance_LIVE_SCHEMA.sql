-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Migration 019 — PMPD V5 Soft Reset Research Governance
-- LIVE-SCHEMA SAFE VERSION
-- Generated: 2026-09-04
--
-- Built directly from the live schemas supplied by the user.
--
-- Conservative design:
--   * Uses strategy_id everywhere (matching live schema)
--   * Uses public.strategies.strategy_code='PMPD' to resolve the strategy
--   * No CREATE TABLE / ALTER TABLE / RLS changes
--   * No ON CONFLICT assumptions
--   * Does not modify the existing PMPD-RM-1.0 research_factors inventory
--   * Does not alter frozen V4 logic
--   * Transaction rolls back automatically on any validation failure
-- ============================================================================

begin;

-- --------------------------------------------------------------------------
-- 0. PRE-FLIGHT: exactly one PMPD strategy must exist
-- --------------------------------------------------------------------------
do $$
declare
    v_count integer;
begin
    select count(*)
    into v_count
    from public.strategies
    where strategy_code = 'PMPD';

    if v_count <> 1 then
        raise exception
            'Migration 019 pre-flight failed: expected exactly one PMPD strategy; found %.',
            v_count;
    end if;
end
$$;

-- --------------------------------------------------------------------------
-- 1. V5 ROADMAP SOURCE
--    First update any rows that already exist.
-- --------------------------------------------------------------------------
with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
),
phases(
    phase_code,
    phase_name,
    objective,
    status,
    sequence_order,
    entry_criteria,
    exit_criteria,
    next_phase_code,
    notes
) as (
    values
    ('9A','V5 Soft Reset & Research Architecture',
     'Freeze V4 as benchmark and define the V5 research-first architecture.',
     'complete',901,
     'V4 exists as stable benchmark.',
     'V5 charter, guardrails, and research-first principles defined.',
     '9B',
     'Completed before Alpha implementation.'),

    ('9B','Existing-Evidence Inventory',
     'Inventory reusable PMPD, Second 1M, data-platform, and governance evidence without importing conclusions.',
     'complete',902,
     '9A complete.',
     'Reusable evidence and infrastructure map documented.',
     '9C',
     'Methodology may transfer; conclusions and thresholds do not.'),

    ('9C','PM+PD Event Taxonomy & State Machine V2',
     'Define event-based PM/AH/PD structural population and state/transition vocabulary.',
     'complete',903,
     '9B complete.',
     'Directional Level-Stack Encounter, structural states, vectors, and decision points defined.',
     '9D',
     'State is not signal; identity-space and geometry-space are both preserved.'),

    ('9D','Warning / Failure Engine Architecture',
     'Define warning/failure research architecture and preserve failure/reclaim branches.',
     'complete',904,
     '9C complete.',
     'Warning/failure families integrated into the V5 research architecture.',
     '9E',
     'No warning threshold is treated as validated V5 truth.'),

    ('9E','Master Research Factor Inventory / Population Design',
     'Define the event population and research families while avoiding V4-signal selection bias.',
     'complete',905,
     '9D complete.',
     'Event-based population and continuous-factor-first approach established.',
     '9F',
     'Existing PMPD-RM-1.0 remains preserved pending explicit V5 factor-map migration.'),

    ('9F','Dataset & Measurement Architecture',
     'Define six-level reconstruction, geometry, vectors, transitions, decision points, outcomes, and reproducibility rules.',
     'complete',906,
     '9E complete.',
     'Alpha architecture and certified-data integration implemented.',
     '9G',
     'Uses PMH/AHH/PDH and PML/AHL/PDL; completed-bar reproducibility preserved.'),

    ('9G','Large-Sample Baseline / Event Population',
     'Certify the structural engine and characterize the full-universe natural event population before profitability research.',
     'active',907,
     '9F complete and Alpha structural engine implemented.',
     'Full-universe structural baseline passes integrity, export, discontinuity, and population audits.',
     '9H',
     'Current substep: 9G-3B/9G-3C. Alpha 0.2.1 corrected full-universe run pending local completion/upload.'),

    ('9H','Individual Factor Research',
     'Test individual V5 factors against frozen outcome definitions using discovery-only threshold selection and robustness gates.',
     'ready',908,
     '9G structural certification complete.',
     'Priority individual factors tested with sample-size, CI, concentration, stability, and multiple-comparison controls.',
     '9I',
     'Do not begin factor optimization until 9G closes.'),

    ('9I','Factor Interaction & Archetype Research',
     'Test interactions and recurring structural archetypes after individual-factor evidence exists.',
     'backlog',909,
     '9H priority factors complete.',
     'Stable interactions/archetypes identified or rejected.',
     '9J',
     null),

    ('9J','Alternative Entry / Confirmation Architectures',
     'Compare alternative entry/confirmation architectures, including event transitions and reclaim/rejection structures.',
     'backlog',910,
     '9I evidence available.',
     'Candidate entry architectures compared without changing frozen V4.',
     '9K',
     'Includes the dedicated Alternative C2 Entry Architecture research branch where applicable.'),

    ('9K','Evidence-Derived Classification / Scoring',
     'Build classification/scoring only from demonstrated evidence rather than inherited weights.',
     'backlog',911,
     '9J complete.',
     'Candidate classification/scoring architecture documented and reproducible.',
     '9L',
     null),

    ('9L','V5 Candidate Model Freeze',
     'Freeze one V5 candidate and its complete rules before untouched validation.',
     'backlog',912,
     '9K complete.',
     'Candidate rules, thresholds, code/data versions, and exclusions frozen.',
     '9M',
     null),

    ('9M','Out-of-Sample Validation',
     'Evaluate the frozen V5 candidate on untouched out-of-sample data.',
     'backlog',913,
     '9L candidate frozen.',
     'OOS results and robustness decision recorded.',
     '9N',
     null),

    ('9N','V4 vs V5 Head-to-Head',
     'Compare frozen V5 candidate directly with frozen V4 on common evidence.',
     'backlog',914,
     '9M complete.',
     'Head-to-head comparison completed with common definitions and datasets.',
     '9O',
     null),

    ('9O','Prospective Validation',
     'Validate the frozen candidate prospectively without research-time modification.',
     'backlog',915,
     '9N supports continued validation.',
     'Prospective evidence reaches predefined review gate.',
     '9P',
     null),

    ('9P','Production Pine Implementation',
     'Implement only the validated production candidate in Pine after research gates pass.',
     'backlog',916,
     '9O passes.',
     'Production implementation achieves parity with frozen validated specification.',
     null,
     'No production rewrite before this phase.')
)
update public.program_phases pp
set
    phase_name      = ph.phase_name,
    objective       = ph.objective,
    status          = ph.status,
    sequence_order  = ph.sequence_order,
    entry_criteria  = ph.entry_criteria,
    exit_criteria   = ph.exit_criteria,
    next_phase_code = ph.next_phase_code,
    notes           = ph.notes,
    started_at      = case
        when pp.started_at is not null then pp.started_at
        when ph.status in ('active','complete') then now()
        else null
    end,
    completed_at    = case
        when ph.status = 'complete' then coalesce(pp.completed_at, now())
        else pp.completed_at
    end,
    updated_at      = now()
from pmpd
cross join phases ph
where pp.strategy_id = pmpd.strategy_id
  and pp.phase_code = ph.phase_code;

-- --------------------------------------------------------------------------
-- 2. INSERT ANY MISSING V5 PHASE ROWS
-- --------------------------------------------------------------------------
with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
),
phases(
    phase_code,
    phase_name,
    objective,
    status,
    sequence_order,
    entry_criteria,
    exit_criteria,
    next_phase_code,
    notes
) as (
    values
    ('9A','V5 Soft Reset & Research Architecture',
     'Freeze V4 as benchmark and define the V5 research-first architecture.',
     'complete',901,
     'V4 exists as stable benchmark.',
     'V5 charter, guardrails, and research-first principles defined.',
     '9B',
     'Completed before Alpha implementation.'),

    ('9B','Existing-Evidence Inventory',
     'Inventory reusable PMPD, Second 1M, data-platform, and governance evidence without importing conclusions.',
     'complete',902,
     '9A complete.',
     'Reusable evidence and infrastructure map documented.',
     '9C',
     'Methodology may transfer; conclusions and thresholds do not.'),

    ('9C','PM+PD Event Taxonomy & State Machine V2',
     'Define event-based PM/AH/PD structural population and state/transition vocabulary.',
     'complete',903,
     '9B complete.',
     'Directional Level-Stack Encounter, structural states, vectors, and decision points defined.',
     '9D',
     'State is not signal; identity-space and geometry-space are both preserved.'),

    ('9D','Warning / Failure Engine Architecture',
     'Define warning/failure research architecture and preserve failure/reclaim branches.',
     'complete',904,
     '9C complete.',
     'Warning/failure families integrated into the V5 research architecture.',
     '9E',
     'No warning threshold is treated as validated V5 truth.'),

    ('9E','Master Research Factor Inventory / Population Design',
     'Define the event population and research families while avoiding V4-signal selection bias.',
     'complete',905,
     '9D complete.',
     'Event-based population and continuous-factor-first approach established.',
     '9F',
     'Existing PMPD-RM-1.0 remains preserved pending explicit V5 factor-map migration.'),

    ('9F','Dataset & Measurement Architecture',
     'Define six-level reconstruction, geometry, vectors, transitions, decision points, outcomes, and reproducibility rules.',
     'complete',906,
     '9E complete.',
     'Alpha architecture and certified-data integration implemented.',
     '9G',
     'Uses PMH/AHH/PDH and PML/AHL/PDL; completed-bar reproducibility preserved.'),

    ('9G','Large-Sample Baseline / Event Population',
     'Certify the structural engine and characterize the full-universe natural event population before profitability research.',
     'active',907,
     '9F complete and Alpha structural engine implemented.',
     'Full-universe structural baseline passes integrity, export, discontinuity, and population audits.',
     '9H',
     'Current substep: 9G-3B/9G-3C. Alpha 0.2.1 corrected full-universe run pending local completion/upload.'),

    ('9H','Individual Factor Research',
     'Test individual V5 factors against frozen outcome definitions using discovery-only threshold selection and robustness gates.',
     'ready',908,
     '9G structural certification complete.',
     'Priority individual factors tested with sample-size, CI, concentration, stability, and multiple-comparison controls.',
     '9I',
     'Do not begin factor optimization until 9G closes.'),

    ('9I','Factor Interaction & Archetype Research',
     'Test interactions and recurring structural archetypes after individual-factor evidence exists.',
     'backlog',909,
     '9H priority factors complete.',
     'Stable interactions/archetypes identified or rejected.',
     '9J',
     null),

    ('9J','Alternative Entry / Confirmation Architectures',
     'Compare alternative entry/confirmation architectures, including event transitions and reclaim/rejection structures.',
     'backlog',910,
     '9I evidence available.',
     'Candidate entry architectures compared without changing frozen V4.',
     '9K',
     'Includes the dedicated Alternative C2 Entry Architecture research branch where applicable.'),

    ('9K','Evidence-Derived Classification / Scoring',
     'Build classification/scoring only from demonstrated evidence rather than inherited weights.',
     'backlog',911,
     '9J complete.',
     'Candidate classification/scoring architecture documented and reproducible.',
     '9L',
     null),

    ('9L','V5 Candidate Model Freeze',
     'Freeze one V5 candidate and its complete rules before untouched validation.',
     'backlog',912,
     '9K complete.',
     'Candidate rules, thresholds, code/data versions, and exclusions frozen.',
     '9M',
     null),

    ('9M','Out-of-Sample Validation',
     'Evaluate the frozen V5 candidate on untouched out-of-sample data.',
     'backlog',913,
     '9L candidate frozen.',
     'OOS results and robustness decision recorded.',
     '9N',
     null),

    ('9N','V4 vs V5 Head-to-Head',
     'Compare frozen V5 candidate directly with frozen V4 on common evidence.',
     'backlog',914,
     '9M complete.',
     'Head-to-head comparison completed with common definitions and datasets.',
     '9O',
     null),

    ('9O','Prospective Validation',
     'Validate the frozen candidate prospectively without research-time modification.',
     'backlog',915,
     '9N supports continued validation.',
     'Prospective evidence reaches predefined review gate.',
     '9P',
     null),

    ('9P','Production Pine Implementation',
     'Implement only the validated production candidate in Pine after research gates pass.',
     'backlog',916,
     '9O passes.',
     'Production implementation achieves parity with frozen validated specification.',
     null,
     'No production rewrite before this phase.')
)
insert into public.program_phases (
    strategy_id,
    phase_code,
    phase_name,
    objective,
    status,
    sequence_order,
    entry_criteria,
    exit_criteria,
    started_at,
    completed_at,
    next_phase_code,
    notes
)
select
    pmpd.strategy_id,
    ph.phase_code,
    ph.phase_name,
    ph.objective,
    ph.status,
    ph.sequence_order,
    ph.entry_criteria,
    ph.exit_criteria,
    case when ph.status in ('active','complete') then now() else null end,
    case when ph.status = 'complete' then now() else null end,
    ph.next_phase_code,
    ph.notes
from pmpd
cross join phases ph
where not exists (
    select 1
    from public.program_phases pp
    where pp.strategy_id = pmpd.strategy_id
      and pp.phase_code = ph.phase_code
);

-- --------------------------------------------------------------------------
-- 3. RECORD V5 GOVERNANCE DECISIONS
-- --------------------------------------------------------------------------
with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
),
decisions(
    title,
    decision,
    rationale,
    evidence,
    affects_model_version,
    metadata_json
) as (
    values
    (
      'PMPD V5 is a research-first soft reset with V4 frozen as benchmark',
      'V5 may challenge assumptions above the core PM/AH/PD market concept, while V4 remains frozen and unchanged as the benchmark/reference implementation.',
      'Prevents research changes from contaminating the benchmark and allows V5 to earn adoption through evidence.',
      'V5 roadmap phases 9A-9P and Alpha structural certification work.',
      'V5',
      jsonb_build_object(
          'governance_version','PMPD-V5-GOV-1.0',
          'v4_status','FROZEN_BENCHMARK'
      )
    ),
    (
      'PMPD V5 research population is event-based rather than V4-signal-based',
      'The primary V5 research unit is the Directional Level-Stack Encounter, not the existing V4 signal population.',
      'Avoids conditioning the research population on V4 confirmation assumptions and reduces selection bias.',
      '9C-9G architecture; PMH/AHH/PDH and PML/AHL/PDL structural engine.',
      'V5',
      jsonb_build_object(
          'population_unit','DIRECTIONAL_LEVEL_STACK_ENCOUNTER'
      )
    ),
    (
      'PMPD V5 preserves all PM/AH/PD session extremes',
      'Bullish identity-space levels are PMH, AHH, PDH; bearish identity-space levels are PML, AHL, PDL. Geometry-space ordering is stored separately.',
      'After-hours information is explicitly required and level identity may carry information distinct from inner/middle/outer geometry.',
      '9C-9G six-level architecture.',
      'V5',
      jsonb_build_object(
          'bull_levels',jsonb_build_array('PMH','AHH','PDH'),
          'bear_levels',jsonb_build_array('PML','AHL','PDL')
      )
    ),
    (
      'PMPD V5 structural certification precedes profitability research',
      'Large-sample event structure, session quality, determinism, geometry, transitions, and export integrity must pass before factor/outcome optimization begins.',
      'Reduces the risk of optimizing against implementation or data-quality defects.',
      'Alpha 0.1 deterministic 5x10 certification and Alpha 0.2 full-universe structural baseline.',
      'V5',
      jsonb_build_object(
          'current_gate','9G',
          'outcome_blinding','ENABLED_DURING_STRUCTURAL_CERTIFICATION'
      )
    )
)
insert into public.project_decisions (
    strategy_id,
    title,
    decision,
    rationale,
    evidence,
    affects_model_version,
    metadata_json
)
select
    pmpd.strategy_id,
    d.title,
    d.decision,
    d.rationale,
    d.evidence,
    d.affects_model_version,
    d.metadata_json
from pmpd
cross join decisions d
where not exists (
    select 1
    from public.project_decisions x
    where x.strategy_id = pmpd.strategy_id
      and x.title = d.title
      and x.status = 'active'
);

-- --------------------------------------------------------------------------
-- 4. UPDATE EXISTING PMPD PROJECT STATE
-- --------------------------------------------------------------------------
with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
update public.project_state ps
set
    active_phase_code = '9G',
    active_phase_name = 'Large-Sample Baseline / Event Population',
    next_phase_code = '9H',
    next_phase_name = 'Individual Factor Research',
    blocker_count = 0,
    baseline_model = 'V4 Forward Validation FINAL',
    baseline_status = 'FROZEN_BENCHMARK',
    historical_dataset_status =
        'PMPD_112_V1 / 2025 CERTIFIED; V5 STRUCTURAL AUDIT ACTIVE',
    last_decision =
        'V5 Alpha 0.2.1 export/data-integrity hardening run pending; close 9G before exposing factor research to outcomes.',
    roadmap_version = 'PMPD-V5-GOV-1.0',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            'v5_governance_version','PMPD-V5-GOV-1.0',
            'v5_phase_roadmap','9A-9P',
            'v5_current_substep','9G-3B/9G-3C',
            'v5_alpha_version','0.2.1',
            'v5_structural_population','EVENT_BASED',
            'v5_outcome_blinding','STRUCTURAL_CERTIFICATION_ONLY',
            'v4_frozen_benchmark',true,
            'v5_levels',jsonb_build_object(
                'bull',jsonb_build_array('PMH','AHH','PDH'),
                'bear',jsonb_build_array('PML','AHL','PDL')
            ),
            'factor_roadmap_note',
            'PMPD-RM-1.0 preserved; V5 factor remap/version migration deferred until 9G closes'
        ),
    updated_at = now()
from pmpd
where ps.strategy_id = pmpd.strategy_id;

-- --------------------------------------------------------------------------
-- 5. VALIDATION
-- --------------------------------------------------------------------------
do $$
declare
    v_strategy_id uuid;
    v_phase_count integer;
    v_active_count integer;
    v_state_count integer;
begin
    select strategy_id
    into v_strategy_id
    from public.strategies
    where strategy_code = 'PMPD';

    select count(*)
    into v_phase_count
    from public.program_phases
    where strategy_id = v_strategy_id
      and phase_code in (
          '9A','9B','9C','9D','9E','9F','9G','9H',
          '9I','9J','9K','9L','9M','9N','9O','9P'
      );

    if v_phase_count <> 16 then
        raise exception
            'Migration 019 validation failed: expected 16 V5 phases, found %.',
            v_phase_count;
    end if;

    select count(*)
    into v_active_count
    from public.program_phases
    where strategy_id = v_strategy_id
      and phase_code in (
          '9A','9B','9C','9D','9E','9F','9G','9H',
          '9I','9J','9K','9L','9M','9N','9O','9P'
      )
      and status = 'active';

    if v_active_count <> 1 then
        raise exception
            'Migration 019 validation failed: expected exactly 1 active V5 phase, found %.',
            v_active_count;
    end if;

    select count(*)
    into v_state_count
    from public.project_state
    where strategy_id = v_strategy_id
      and active_phase_code = '9G'
      and next_phase_code = '9H'
      and baseline_status = 'FROZEN_BENCHMARK';

    if v_state_count <> 1 then
        raise exception
            'Migration 019 validation failed: expected project_state active=9G, next=9H, baseline frozen.';
    end if;
end
$$;

commit;

-- --------------------------------------------------------------------------
-- 6. POST-MIGRATION READOUT
-- --------------------------------------------------------------------------
with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
select
    pp.phase_code,
    pp.phase_name,
    pp.status,
    pp.sequence_order,
    pp.next_phase_code
from public.program_phases pp
join pmpd on pmpd.strategy_id = pp.strategy_id
where pp.phase_code in (
    '9A','9B','9C','9D','9E','9F','9G','9H',
    '9I','9J','9K','9L','9M','9N','9O','9P'
)
order by pp.sequence_order;

with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
select
    ps.active_phase_code,
    ps.active_phase_name,
    ps.next_phase_code,
    ps.next_phase_name,
    ps.baseline_model,
    ps.baseline_status,
    ps.historical_dataset_status,
    ps.roadmap_version,
    ps.last_decision
from public.project_state ps
join pmpd on pmpd.strategy_id = ps.strategy_id;
