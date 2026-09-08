-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Migration 019 — PMPD V5 Soft Reset Research Governance (CORRECTED)
-- Generated: 2026-09-04
--
-- PURPOSE
--   1) Persist the V5 phase roadmap (9A–9P) in the existing shared platform.
--   2) Record the V5 soft-reset governance decisions.
--   3) Move project_state to the current V5 research position.
--   4) Preserve V4 as the frozen benchmark and PMPD-RM-1.0 as historical roadmap.
--
-- IMPORTANT
--   * Uses the existing schema's project_key='PMPD' model.
--   * Does NOT alter frozen V4 signal logic.
--   * Does NOT replace the PMPD-RM-1.0 factor inventory.
--   * Idempotent for roadmap rows and decision titles.
-- ============================================================================

begin;

-- --------------------------------------------------------------------------
-- 1. V5 PROGRAM PHASE ROADMAP
-- --------------------------------------------------------------------------
with phases(phase_code, phase_name, objective, status, sequence_order,
            entry_criteria, exit_criteria, next_phase_code, notes) as (
    values
    ('9A','V5 Soft Reset & Research Architecture',
     'Freeze V4 as benchmark and define the V5 research-first architecture.',
     'complete', 901,
     'V4 exists as stable benchmark.',
     'V5 charter, guardrails, and research-first principles defined.',
     '9B','Completed before Alpha implementation.'),

    ('9B','Existing-Evidence Inventory',
     'Inventory reusable PMPD, Second 1M, data-platform, and governance evidence without importing conclusions.',
     'complete', 902,
     '9A complete.',
     'Reusable evidence and infrastructure map documented.',
     '9C','Methodology may transfer; conclusions and thresholds do not.'),

    ('9C','PM+PD Event Taxonomy & State Machine V2',
     'Define event-based PM/AH/PD structural population and state/transition vocabulary.',
     'complete', 903,
     '9B complete.',
     'Directional Level-Stack Encounter, structural states, vectors, and decision points defined.',
     '9D','State is not signal; identity-space and geometry-space are both preserved.'),

    ('9D','Warning / Failure Engine Architecture',
     'Define warning/failure research architecture and preserve failure/reclaim branches.',
     'complete', 904,
     '9C complete.',
     'Warning/failure families integrated into the V5 research architecture.',
     '9E','No warning threshold is treated as validated V5 truth.'),

    ('9E','Master Research Factor Inventory / Population Design',
     'Define the event population and research families while avoiding V4-signal selection bias.',
     'complete', 905,
     '9D complete.',
     'Event-based population and continuous-factor-first approach established.',
     '9F','Existing PMPD-RM-1.0 remains preserved pending explicit V5 factor-map migration.'),

    ('9F','Dataset & Measurement Architecture',
     'Define six-level reconstruction, geometry, vectors, transitions, decision points, outcomes, and reproducibility rules.',
     'complete', 906,
     '9E complete.',
     'Alpha architecture and certified-data integration implemented.',
     '9G','Uses PMH/AHH/PDH and PML/AHL/PDL; completed-bar reproducibility preserved.'),

    ('9G','Large-Sample Baseline / Event Population',
     'Certify the structural engine and characterize the full-universe natural event population before profitability research.',
     'active', 907,
     '9F complete and Alpha structural engine implemented.',
     'Full-universe structural baseline passes integrity, export, discontinuity, and population audits.',
     '9H','Current substep: 9G-3B/3C. Alpha 0.2.1 corrected full-universe run pending local completion/upload.'),

    ('9H','Individual Factor Research',
     'Test individual V5 factors against frozen outcome definitions using discovery-only threshold selection and robustness gates.',
     'ready', 908,
     '9G structural certification complete.',
     'Priority individual factors tested with sample-size, CI, concentration, stability, and multiple-comparison controls.',
     '9I','Do not begin factor optimization until 9G closes.'),

    ('9I','Factor Interaction & Archetype Research',
     'Test interactions and recurring structural archetypes after individual-factor evidence exists.',
     'backlog', 909,
     '9H priority factors complete.',
     'Stable interactions/archetypes identified or rejected.',
     '9J',null),

    ('9J','Alternative Entry / Confirmation Architectures',
     'Compare alternative entry/confirmation architectures, including event transitions and reclaim/rejection structures.',
     'backlog', 910,
     '9I evidence available.',
     'Candidate entry architectures compared without changing frozen V4.',
     '9K','Includes the dedicated Alternative C2 Entry Architecture research branch where applicable.'),

    ('9K','Evidence-Derived Classification / Scoring',
     'Build classification/scoring only from demonstrated evidence rather than inherited weights.',
     'backlog', 911,
     '9J complete.',
     'Candidate classification/scoring architecture documented and reproducible.',
     '9L',null),

    ('9L','V5 Candidate Model Freeze',
     'Freeze one V5 candidate and its complete rules before untouched validation.',
     'backlog', 912,
     '9K complete.',
     'Candidate rules, thresholds, code/data versions, and exclusions frozen.',
     '9M',null),

    ('9M','Out-of-Sample Validation',
     'Evaluate the frozen V5 candidate on untouched out-of-sample data.',
     'backlog', 913,
     '9L candidate frozen.',
     'OOS results and robustness decision recorded.',
     '9N',null),

    ('9N','V4 vs V5 Head-to-Head',
     'Compare frozen V5 candidate directly with frozen V4 on common evidence.',
     'backlog', 914,
     '9M complete.',
     'Head-to-head comparison completed with common definitions and datasets.',
     '9O',null),

    ('9O','Prospective Validation',
     'Validate the frozen candidate prospectively without research-time modification.',
     'backlog', 915,
     '9N supports continued validation.',
     'Prospective evidence reaches predefined review gate.',
     '9P',null),

    ('9P','Production Pine Implementation',
     'Implement only the validated production candidate in Pine after research gates pass.',
     'backlog', 916,
     '9O passes.',
     'Production implementation achieves parity with frozen validated specification.',
     null,'No production rewrite before this phase.')
)
insert into public.program_phases (
    project_key, phase_code, phase_name, objective, status, sequence_order,
    entry_criteria, exit_criteria, next_phase_code, notes,
    started_at, completed_at
)
select
    'PMPD',
    ph.phase_code, ph.phase_name, ph.objective, ph.status, ph.sequence_order,
    ph.entry_criteria, ph.exit_criteria, ph.next_phase_code, ph.notes,
    case when ph.status in ('active','complete') then now() else null end,
    case when ph.status = 'complete' then now() else null end
from phases ph
on conflict (project_key, phase_code) do update
set
    phase_name = excluded.phase_name,
    objective = excluded.objective,
    status = excluded.status,
    sequence_order = excluded.sequence_order,
    entry_criteria = excluded.entry_criteria,
    exit_criteria = excluded.exit_criteria,
    next_phase_code = excluded.next_phase_code,
    notes = excluded.notes,
    started_at = coalesce(public.program_phases.started_at, excluded.started_at),
    completed_at = case
        when excluded.status = 'complete'
            then coalesce(public.program_phases.completed_at, excluded.completed_at)
        else public.program_phases.completed_at
    end,
    updated_at = now();

-- --------------------------------------------------------------------------
-- 2. GOVERNANCE DECISIONS
-- --------------------------------------------------------------------------
with decisions(title, decision, rationale, evidence, affects_model_version, metadata_json) as (
    values
    (
      'PMPD V5 is a research-first soft reset with V4 frozen as benchmark',
      'V5 may challenge assumptions above the core PM/AH/PD market concept, while V4 remains frozen and unchanged as the benchmark/reference implementation.',
      'Prevents research changes from contaminating the benchmark and allows V5 to earn adoption through evidence.',
      'V5 roadmap phases 9A-9P and Alpha structural certification work.',
      'V5',
      jsonb_build_object('governance_version','PMPD-V5-GOV-1.0','v4_status','FROZEN_BENCHMARK')
    ),
    (
      'PMPD V5 research population is event-based rather than V4-signal-based',
      'The primary V5 research unit is the Directional Level-Stack Encounter, not the existing V4 signal population.',
      'Avoids conditioning the research population on V4 confirmation assumptions and reduces selection bias.',
      '9C-9G architecture; PMH/AHH/PDH and PML/AHL/PDL structural engine.',
      'V5',
      jsonb_build_object('population_unit','DIRECTIONAL_LEVEL_STACK_ENCOUNTER')
    ),
    (
      'PMPD V5 preserves all PM/AH/PD session extremes',
      'Bullish identity-space levels are PMH, AHH, PDH; bearish identity-space levels are PML, AHL, PDL. Geometry-space ordering is stored separately.',
      'After-hours information is explicitly required and level identity may carry information distinct from inner/middle/outer geometry.',
      '9C-9G six-level architecture.',
      'V5',
      jsonb_build_object('bull_levels',jsonb_build_array('PMH','AHH','PDH'),
                         'bear_levels',jsonb_build_array('PML','AHL','PDL'))
    ),
    (
      'PMPD V5 structural certification precedes profitability research',
      'Large-sample event structure, session quality, determinism, geometry, transitions, and export integrity must pass before factor/outcome optimization begins.',
      'Reduces the risk of optimizing against implementation or data-quality defects.',
      'Alpha 0.1 deterministic 5x10 certification and Alpha 0.2 full-universe structural baseline.',
      'V5',
      jsonb_build_object('current_gate','9G','outcome_blinding','ENABLED_DURING_STRUCTURAL_CERTIFICATION')
    )
)
insert into public.project_decisions (
    project_key, title, decision, rationale, evidence, affects_model_version, metadata_json
)
select 'PMPD', d.title, d.decision, d.rationale, d.evidence,
       d.affects_model_version, d.metadata_json
from decisions d
where not exists (
    select 1
    from public.project_decisions x
    where x.project_key = 'PMPD'
      and x.title = d.title
      and x.status = 'active'
);

-- --------------------------------------------------------------------------
-- 3. PROJECT STATE
-- --------------------------------------------------------------------------
insert into public.project_state (
    project_key,
    active_phase_code, active_phase_name,
    next_phase_code, next_phase_name,
    baseline_model, baseline_status,
    historical_dataset_status,
    last_decision,
    roadmap_version,
    metadata_json
)
values (
    'PMPD',
    '9G','Large-Sample Baseline / Event Population',
    '9H','Individual Factor Research',
    'V4 Forward Validation FINAL','FROZEN_BENCHMARK',
    'PMPD_112_V1 / 2025 CERTIFIED; V5 STRUCTURAL AUDIT ACTIVE',
    'V5 Alpha 0.2.1 export/data-integrity hardening run pending; close 9G before exposing factor research to outcomes.',
    'PMPD-V5-GOV-1.0',
    jsonb_build_object(
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
        'factor_roadmap_note','PMPD-RM-1.0 preserved; V5 factor remap/version migration deferred until 9G closes'
    )
)
on conflict (project_key) do update
set
    active_phase_code = excluded.active_phase_code,
    active_phase_name = excluded.active_phase_name,
    next_phase_code = excluded.next_phase_code,
    next_phase_name = excluded.next_phase_name,
    baseline_model = excluded.baseline_model,
    baseline_status = excluded.baseline_status,
    historical_dataset_status = excluded.historical_dataset_status,
    last_decision = excluded.last_decision,
    roadmap_version = excluded.roadmap_version,
    metadata_json = coalesce(public.project_state.metadata_json, '{}'::jsonb) || excluded.metadata_json,
    updated_at = now();

-- --------------------------------------------------------------------------
-- 4. VALIDATION
-- --------------------------------------------------------------------------
do $$
declare
    v_v5_phases integer;
    v_active integer;
begin
    select count(*) into v_v5_phases
    from public.program_phases
    where project_key = 'PMPD'
      and phase_code in ('9A','9B','9C','9D','9E','9F','9G','9H','9I','9J','9K','9L','9M','9N','9O','9P');

    if v_v5_phases <> 16 then
        raise exception 'V5 roadmap validation failed: expected 16 phases, found %.', v_v5_phases;
    end if;

    select count(*) into v_active
    from public.program_phases
    where project_key = 'PMPD'
      and phase_code in ('9A','9B','9C','9D','9E','9F','9G','9H','9I','9J','9K','9L','9M','9N','9O','9P')
      and status = 'active';

    if v_active <> 1 then
        raise exception 'V5 roadmap validation failed: expected exactly 1 active V5 phase, found %.', v_active;
    end if;

    if not exists (
        select 1
        from public.project_state
        where project_key = 'PMPD'
          and active_phase_code = '9G'
          and next_phase_code = '9H'
    ) then
        raise exception 'project_state validation failed: expected active 9G and next 9H.';
    end if;
end $$;

commit;

-- Recommended post-migration check:
--   Run sql/dashboard/07_pmpd_governance_vertical.sql
