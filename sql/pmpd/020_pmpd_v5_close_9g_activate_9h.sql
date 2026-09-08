-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Migration 020 — Close 9G / Activate 9H / Synchronize V5 Status, Plan, Roadmap
-- Generated: 2026-09-04
--
-- Preconditions:
--   * Migration 019 live-schema version completed successfully.
--   * PMPD V5 Alpha 0.2.1 full-universe structural package audited.
--
-- Audit basis:
--   protocol: PMPD_V5_ALPHA_0_2_FULL_UNIVERSE_STRUCTURAL_V1
--   fingerprint: 069540a5425c05f5b632163598bfcb3b469d210e53bd03ef539613864afcda1f
--   symbols: 112
--   events: 44,627
--   transitions: 793,820
--   decision points: 450,491
--
-- Governance:
--   * 9G closes PASS WITH DATA-QUALITY GUARDRAILS.
--   * 9H becomes ACTIVE.
--   * V4 remains frozen benchmark.
--   * PMPD-RM-1.0 remains preserved until V5 factor-roadmap remap/versioning.
--   * Supabase capacity is currently not a database constraint.
-- ============================================================================

begin;

-- --------------------------------------------------------------------------
-- 0. PRE-FLIGHT
-- --------------------------------------------------------------------------
do $$
declare
    v_strategy_count integer;
    v_phase_9g integer;
    v_phase_9h integer;
begin
    select count(*)
    into v_strategy_count
    from public.strategies
    where strategy_code = 'PMPD';

    if v_strategy_count <> 1 then
        raise exception
            'Migration 020 pre-flight failed: expected exactly one PMPD strategy; found %.',
            v_strategy_count;
    end if;

    select count(*)
    into v_phase_9g
    from public.program_phases pp
    join public.strategies s on s.strategy_id = pp.strategy_id
    where s.strategy_code = 'PMPD'
      and pp.phase_code = '9G';

    select count(*)
    into v_phase_9h
    from public.program_phases pp
    join public.strategies s on s.strategy_id = pp.strategy_id
    where s.strategy_code = 'PMPD'
      and pp.phase_code = '9H';

    if v_phase_9g <> 1 or v_phase_9h <> 1 then
        raise exception
            'Migration 020 pre-flight failed: expected exactly one 9G and one 9H row; found 9G=%, 9H=%.',
            v_phase_9g, v_phase_9h;
    end if;
end
$$;

-- --------------------------------------------------------------------------
-- 1. CLOSE 9G
-- --------------------------------------------------------------------------
with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
update public.program_phases pp
set
    status = 'complete',
    completed_at = coalesce(pp.completed_at, now()),
    notes =
        'PASS WITH DATA-QUALITY GUARDRAILS. Alpha 0.2.1 full-universe structural audit: '
        || '112 symbols; 44,627 events; 793,820 transitions; 450,491 decision points; '
        || 'export hardening verified; vector codes preserved; session symbol retained; '
        || 'coverage medians populated; structural totals/fingerprint unchanged. '
        || 'Extreme price-scale discontinuities and sparse extended-hours observability '
        || 'must be explicitly flagged/classified before primary outcome inference.',
    updated_at = now()
from pmpd
where pp.strategy_id = pmpd.strategy_id
  and pp.phase_code = '9G';

-- --------------------------------------------------------------------------
-- 2. ACTIVATE 9H
-- --------------------------------------------------------------------------
with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
update public.program_phases pp
set
    status = 'active',
    started_at = coalesce(pp.started_at, now()),
    next_phase_code = '9I',
    notes =
        'ACTIVE. 9H begins with: '
        || '(1) data-quality eligibility/flag layer for scale discontinuities and session observability; '
        || '(2) V5 factor-roadmap reconciliation/versioning while preserving PMPD-RM-1.0; '
        || '(3) frozen outcome definitions and discovery/validation split; '
        || '(4) continuous-factor-first individual research with CI, concentration, temporal stability, '
        || 'threshold robustness, and multiple-comparison controls.',
    updated_at = now()
from pmpd
where pp.strategy_id = pmpd.strategy_id
  and pp.phase_code = '9H';

-- --------------------------------------------------------------------------
-- 3. RECORD 9G / 9H GOVERNANCE DECISIONS
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
      'PMPD V5 9G structural certification closes PASS WITH DATA-QUALITY GUARDRAILS',
      'Close phase 9G and authorize phase 9H individual-factor research. The Alpha 0.2.1 structural engine is certified for progression, subject to explicit data-quality flags for scale discontinuities and session observability.',
      'The corrected full-universe package preserved the Alpha 0.2 structural fingerprint and population totals while fixing the known export defects. No event-architecture redesign is required.',
      'Alpha 0.2.1 audit: 112 symbols; 44,627 events; 793,820 transitions; 450,491 decision points; fingerprint 069540a5425c05f5b632163598bfcb3b469d210e53bd03ef539613864afcda1f.',
      'V5',
      jsonb_build_object(
          'phase_closed','9G',
          'phase_opened','9H',
          'verdict','PASS_WITH_DATA_QUALITY_GUARDRAILS',
          'alpha_version','0.2.1',
          'protocol','PMPD_V5_ALPHA_0_2_FULL_UNIVERSE_STRUCTURAL_V1',
          'fingerprint','069540a5425c05f5b632163598bfcb3b469d210e53bd03ef539613864afcda1f',
          'symbol_count',112,
          'events',44627,
          'transitions',793820,
          'decision_points',450491
      )
    ),
    (
      'PMPD V5 9H requires explicit data-quality eligibility and observability flags',
      'Do not silently treat extreme price-scale discontinuities or sparse PM/AH observations as ordinary geometry. Preserve them in raw structural data, add explicit flags/classification, and keep primary inference eligibility auditable.',
      'The structural audit found a small number of extreme scale mismatches consistent with corporate-action/price-scale boundaries and substantial variation in PM/AH bar observability. These are data-quality dimensions, not evidence for or against the trading hypothesis.',
      'Alpha 0.2.1 session_levels and geometry audit.',
      'V5',
      jsonb_build_object(
          'guardrail_type','DATA_QUALITY',
          'raw_data_preserved',true,
          'silent_exclusion',false,
          'requires_classification',true
      )
    ),
    (
      'Supabase capacity is not a current PMPD research constraint',
      'Continue PMPD V5 research without deleting valuable data or constraining the research design around the former Free-tier database limit.',
      'User upgraded Supabase and reports no current database limitation.',
      'Project infrastructure status update recorded at 9H transition.',
      null,
      jsonb_build_object(
          'capacity_status','UPGRADED_NO_CURRENT_DB_LIMITATION',
          'research_constraint',false,
          'archive_strategy_still_valid',true
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
-- 4. TRACK IMMEDIATE 9H PLAN IN PROJECT_BACKLOG
-- --------------------------------------------------------------------------
with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
),
items(
    title,
    description,
    category,
    priority,
    status,
    origin_phase,
    blocking_current_phase,
    why_it_matters
) as (
    values
    (
      'Build V5 data-quality eligibility and observability layer',
      'Classify price-scale discontinuities and preserve PM/AH/RTH observability measures as explicit research fields before primary outcome inference.',
      'data_quality',
      1,
      'active',
      '9H',
      true,
      'Prevents corporate-action scale breaks and sparse extended-hours data from masquerading as predictive market structure.'
    ),
    (
      'Reconcile PMPD-RM-1.0 into a versioned V5 factor roadmap',
      'Map the preserved 205-factor roadmap into the V5 event-based architecture, preserving history and adding V5-native structural factors without overwriting PMPD-RM-1.0.',
      'research_governance',
      2,
      'active',
      '9H',
      true,
      'Creates an auditable factor sequence for individual-factor research and prevents ad hoc factor selection.'
    ),
    (
      'Freeze 9H outcome and discovery-validation protocol',
      'Freeze decision-point outcome definitions, discovery/validation partitioning, threshold-selection rules, confidence reporting, concentration checks, temporal stability checks, and multiple-comparison controls before factor testing.',
      'methodology',
      3,
      'ready',
      '9H',
      true,
      'Prevents threshold leakage and outcome-driven methodology changes during individual-factor research.'
    )
)
insert into public.project_backlog (
    strategy_id,
    title,
    description,
    category,
    priority,
    status,
    origin_phase,
    blocking_current_phase,
    why_it_matters
)
select
    pmpd.strategy_id,
    i.title,
    i.description,
    i.category,
    i.priority,
    i.status,
    i.origin_phase,
    i.blocking_current_phase,
    i.why_it_matters
from pmpd
cross join items i
where not exists (
    select 1
    from public.project_backlog b
    where b.strategy_id = pmpd.strategy_id
      and b.title = i.title
      and b.status <> 'complete'
);

-- --------------------------------------------------------------------------
-- 5. UPDATE PROJECT STATE: 9H ACTIVE / 9I NEXT
-- --------------------------------------------------------------------------
with pmpd as (
    select strategy_id
    from public.strategies
    where strategy_code = 'PMPD'
)
update public.project_state ps
set
    active_phase_code = '9H',
    active_phase_name = 'Individual Factor Research',
    next_phase_code = '9I',
    next_phase_name = 'Factor Interaction & Archetype Research',
    blocker_count = 0,
    baseline_model = 'V4 Forward Validation FINAL',
    baseline_status = 'FROZEN_BENCHMARK',
    historical_dataset_status =
        'PMPD_112_V1 / 2025 CERTIFIED; V5 ALPHA 0.2.1 STRUCTURAL CERTIFIED; 9H ACTIVE',
    last_decision =
        '9G closed PASS WITH DATA-QUALITY GUARDRAILS; 9H individual-factor research authorized.',
    roadmap_version = 'PMPD-V5-GOV-1.1',
    metadata_json =
        coalesce(ps.metadata_json, '{}'::jsonb)
        || jsonb_build_object(
            'v5_governance_version','PMPD-V5-GOV-1.1',
            'v5_current_phase','9H',
            'v5_current_substep','9H-1',
            'v5_alpha_version','0.2.1',
            'v5_structural_certification','PASS_WITH_DATA_QUALITY_GUARDRAILS',
            'v5_structural_protocol','PMPD_V5_ALPHA_0_2_FULL_UNIVERSE_STRUCTURAL_V1',
            'v5_structural_fingerprint','069540a5425c05f5b632163598bfcb3b469d210e53bd03ef539613864afcda1f',
            'v5_structural_counts',jsonb_build_object(
                'symbols',112,
                'events',44627,
                'transitions',793820,
                'decision_points',450491
            ),
            'v5_9h_plan',jsonb_build_array(
                '9H-1 Data-quality eligibility and session-observability layer',
                '9H-2 V5 factor-roadmap reconciliation/versioning',
                '9H-3 Outcome and discovery-validation protocol freeze',
                '9H-4 Individual continuous-factor research batches',
                '9H-5 Directional/stability/robustness synthesis'
            ),
            'supabase_capacity_status','UPGRADED_NO_CURRENT_DB_LIMITATION',
            'supabase_capacity_is_research_constraint',false,
            'v4_frozen_benchmark',true
        ),
    updated_at = now()
from pmpd
where ps.strategy_id = pmpd.strategy_id;

-- --------------------------------------------------------------------------
-- 6. VALIDATION
-- --------------------------------------------------------------------------
do $$
declare
    v_strategy_id uuid;
    v_9g_status text;
    v_9h_status text;
    v_state_count integer;
    v_active_v5_count integer;
begin
    select strategy_id
    into v_strategy_id
    from public.strategies
    where strategy_code = 'PMPD';

    select status into v_9g_status
    from public.program_phases
    where strategy_id = v_strategy_id
      and phase_code = '9G';

    select status into v_9h_status
    from public.program_phases
    where strategy_id = v_strategy_id
      and phase_code = '9H';

    if v_9g_status <> 'complete' then
        raise exception 'Migration 020 validation failed: 9G status is %, expected complete.', v_9g_status;
    end if;

    if v_9h_status <> 'active' then
        raise exception 'Migration 020 validation failed: 9H status is %, expected active.', v_9h_status;
    end if;

    select count(*)
    into v_active_v5_count
    from public.program_phases
    where strategy_id = v_strategy_id
      and phase_code in (
          '9A','9B','9C','9D','9E','9F','9G','9H',
          '9I','9J','9K','9L','9M','9N','9O','9P'
      )
      and status = 'active';

    if v_active_v5_count <> 1 then
        raise exception
            'Migration 020 validation failed: expected exactly one active V5 phase, found %.',
            v_active_v5_count;
    end if;

    select count(*)
    into v_state_count
    from public.project_state
    where strategy_id = v_strategy_id
      and active_phase_code = '9H'
      and next_phase_code = '9I'
      and baseline_status = 'FROZEN_BENCHMARK'
      and roadmap_version = 'PMPD-V5-GOV-1.1';

    if v_state_count <> 1 then
        raise exception
            'Migration 020 validation failed: project_state did not resolve to 9H -> 9I with frozen V4 benchmark.';
    end if;
end
$$;

commit;

-- --------------------------------------------------------------------------
-- 7. POST-MIGRATION READOUT
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
    ps.last_decision,
    ps.metadata_json ->> 'supabase_capacity_status' as supabase_capacity_status
from public.project_state ps
join pmpd on pmpd.strategy_id = ps.strategy_id;
