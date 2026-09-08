-- ============================================================================
-- PM + PREVIOUS DAY BREAKOUT
-- Migration 021 — PMPD V5 9H Foundations / Factor Roadmap V3 (live-schema fix)
-- Generated: 2026-09-04
-- V3 fixes live research_factors schema compatibility:
--   * supplies required roadmap_version
--   * maps V5 event/decision-point scope to timing_type='mixed'
--   * preserves richer scope in metadata_json
--
-- Completes the first 9H architecture batch:
--   9H-1 data-quality/observability layer
--   9H-2 legacy-roadmap reconciliation + V5-native factor inventory
--   9H-3 frozen individual-factor testing protocol
-- Advances current work to 9H-4A: build outcome research dataset.
--
-- Preserves all 205 PMPD-RM-1.0 rows; adds only V5-native factor codes.
-- ============================================================================

begin;

-- 0. PRE-FLIGHT
do $$
declare
    v_count integer;
begin
    select count(*) into v_count
    from public.strategies where strategy_code='PMPD';
    if v_count <> 1 then
        raise exception 'Migration 021: expected exactly one PMPD strategy, found %.', v_count;
    end if;
end
$$;

-- 1. Seed 48 V5-native factors without modifying the preserved 205 legacy rows.
with pmpd as (
    select strategy_id from public.strategies where strategy_code='PMPD'
),
native_factors(
    factor_code, family, factor_name, description, priority,
    status, timing_type, data_type, data_available, implementation_status
) as (
    values
    ('V5Q01', 'Q_DATA_QUALITY', 'Six-level completeness', 'Whether PMH/PML/AHH/AHL/PDH/PDL are all available for the symbol-day.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5Q02', 'Q_DATA_QUALITY', 'Premarket observation count', 'Number of observed PRE 1-minute bars used to form PMH/PML.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5Q03', 'Q_DATA_QUALITY', 'Prior after-hours observation count', 'Number of observed AH 1-minute bars used to form AHH/AHL.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5Q04', 'Q_DATA_QUALITY', 'Prior RTH observation count', 'Number of observed prior RTH 1-minute bars used to form PDH/PDL.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5Q05', 'Q_DATA_QUALITY', 'Premarket observability tier', 'Descriptive PM observability stratum; retain continuous count as primary field.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5Q06', 'Q_DATA_QUALITY', 'After-hours observability tier', 'Descriptive AH observability stratum; retain continuous count as primary field.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5Q07', 'Q_DATA_QUALITY', 'Six-level price-scale ratio', 'Maximum divided by minimum across all six reconstructed levels.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5Q08', 'Q_DATA_QUALITY', 'Overnight gap percentage', 'Current PM last close versus previous RTH close continuity diagnostic.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5Q09', 'Q_DATA_QUALITY', 'Severe price-scale discontinuity flag', 'Outcome-blind guardrail for obvious corporate-action/scale discontinuities.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5Q10', 'Q_DATA_QUALITY', 'Sparse extended-hours sensitivity flag', 'Whether PM or AH has five or fewer observed bars; not a default exclusion.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5L01', 'L_LEVEL_GEOMETRY', 'Directional stack width percentage', 'Outer-to-inner width of PM/AH/PD directional level stack as percent of price.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5L02', 'L_LEVEL_GEOMETRY', 'ATR-normalized directional stack width', 'Directional stack width normalized by contemporaneous ATR.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5L03', 'L_LEVEL_GEOMETRY', 'PM-AH level separation', 'Directional PM versus AH level separation.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5L04', 'L_LEVEL_GEOMETRY', 'PM-PD level separation', 'Directional PM versus PD level separation.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5L05', 'L_LEVEL_GEOMETRY', 'AH-PD level separation', 'Directional AH versus PD level separation.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5L06', 'L_LEVEL_GEOMETRY', 'Identity ordering inner-to-outer', 'Exact PM/AH/PD identity ordering in directional geometry space.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5L07', 'L_LEVEL_GEOMETRY', 'Inner level identity', 'Whether PM, AH, or PD is the innermost directional level.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5L08', 'L_LEVEL_GEOMETRY', 'Middle level identity', 'Whether PM, AH, or PD is the middle directional level.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5L09', 'L_LEVEL_GEOMETRY', 'Outer level identity', 'Whether PM, AH, or PD is the outermost directional level.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5L10', 'L_LEVEL_GEOMETRY', 'Minimum pairwise confluence distance', 'Smallest pairwise PM/AH/PD directional-level distance.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5L11', 'L_LEVEL_GEOMETRY', 'Levels pre-cleared at RTH open', 'Count of directional levels already beyond price at the RTH open.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5L12', 'L_LEVEL_GEOMETRY', 'RTH open location relative to stack', 'Categorical location of RTH open versus inner/middle/outer levels.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5S01', 'S_EVENT_STRUCTURE', 'First contacted level identity', 'PM/AH/PD identity first contacted by the directional encounter.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5S02', 'S_EVENT_STRUCTURE', 'First cleared level identity', 'PM/AH/PD identity first cleared by the directional encounter.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5S03', 'S_EVENT_STRUCTURE', 'Maximum levels cleared', 'Maximum 0-3 directional levels traded beyond during parent event.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5S04', 'S_EVENT_STRUCTURE', 'First-to-second clear elapsed time', 'Elapsed time between first and second directional clears.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5S05', 'S_EVENT_STRUCTURE', 'Second-to-full-stack clear elapsed time', 'Elapsed time between second clear and first full-stack trade.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5S06', 'S_EVENT_STRUCTURE', 'Contact-to-full-stack elapsed time', 'Elapsed time from first hard contact to first full-stack trade.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5S07', 'S_EVENT_STRUCTURE', 'Traded-beyond vector', 'Three-bit PM/AH/PD vector indicating levels penetrated intrabar.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5S08', 'S_EVENT_STRUCTURE', 'Completed-bar retention vector', 'Three-bit PM/AH/PD vector retained beyond on completed bar.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5S09', 'S_EVENT_STRUCTURE', 'Traded-versus-retained disagreement', 'Difference between traded-beyond and completed-bar retention vectors.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5S10', 'S_EVENT_STRUCTURE', 'Immediate full-stack retention', 'Whether first full-stack trade is retained beyond all three levels on the completed bar.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5S11', 'S_EVENT_STRUCTURE', 'Parent-event attempt count', 'Number of directional attempts within the parent encounter.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5S12', 'S_EVENT_STRUCTURE', 'Attempt number at decision point', 'Attempt ordinal when a candidate decision point occurs.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5S13', 'S_EVENT_STRUCTURE', 'Directional recross count', 'Count of repeated cross/recross transitions through stack levels.', 2, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5S14', 'S_EVENT_STRUCTURE', 'Structural progression path signature', 'Ordered transition signature from contact through clears/losses/reclaims.', 2, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5R01', 'R_FAILURE_RECLAIM', 'Partial loss after retention', 'Whether a retained multi-level structure subsequently loses one or more retained levels.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5R02', 'R_FAILURE_RECLAIM', 'Full loss after retention', 'Whether retained structure subsequently loses all directional levels.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5R03', 'R_FAILURE_RECLAIM', 'Partial reclaim after loss', 'Whether lost structure subsequently reclaims some but not all directional levels.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5R04', 'R_FAILURE_RECLAIM', 'Full reclaim after loss', 'Whether lost structure subsequently reclaims all directional levels.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5R05', 'R_FAILURE_RECLAIM', 'Retention-to-loss elapsed time', 'Elapsed time from retained structure to first partial/full loss.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5R06', 'R_FAILURE_RECLAIM', 'Loss-to-reclaim elapsed time', 'Elapsed time from loss state to partial/full reclaim.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5R07', 'R_FAILURE_RECLAIM', 'Reclaim count', 'Count of reclaim transitions within parent event.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5R08', 'R_FAILURE_RECLAIM', 'Failure-warning persistence', 'Duration/transition count spent in deteriorated or loss states before recovery or termination.', 2, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5T01', 'T_TIMING_VELOCITY', 'Minutes from RTH open to first contact', 'Elapsed RTH minutes before directional stack encounter begins.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5T02', 'T_TIMING_VELOCITY', 'Decision-point time of day', 'Timestamp/minutes since RTH open for each candidate decision point.', 1, 'not_tested', 'decision_point_or_event', 'mixed', true, 'v5_native_available'),
    ('V5T03', 'T_TIMING_VELOCITY', 'Level-crossing velocity', 'Directional price/time velocity across successive stack levels.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned'),
    ('V5T04', 'T_TIMING_VELOCITY', 'Bars between structural transitions', 'Completed 1-minute bars between consecutive state transitions.', 1, 'not_tested', 'decision_point_or_event', 'mixed', false, 'v5_native_planned')
)
insert into public.research_factors (
    strategy_id, factor_code, family, factor_name, description, priority,
    status, timing_type, data_type, data_available, implementation_status,
    metadata_json, roadmap_version
)
select
    pmpd.strategy_id, f.factor_code, f.family, f.factor_name, f.description,
    f.priority, f.status,
    -- Live schema timing_type is constrained to:
    -- signal_time / post_signal / static / mixed.
    -- V5 factors can apply at an event or decision point, so persist the
    -- schema-compatible value 'mixed' and retain the richer V5 scope below.
    'mixed',
    f.data_type, f.data_available, f.implementation_status,
    jsonb_build_object(
        'v5_scope', f.timing_type,
        'seed_source', 'Migration_021',
        'roadmap_family_order', f.priority,
        'v5_native', true
    ),
    'PMPD-V5-RM-2.0'
from pmpd
cross join native_factors f
where not exists (
    select 1 from public.research_factors x
    where x.strategy_id=pmpd.strategy_id and x.factor_code=f.factor_code
);

-- 2. Close the three foundation backlog items created by Migration 020.
with pmpd as (
    select strategy_id from public.strategies where strategy_code='PMPD'
)
update public.project_backlog b
set status='complete', resolved_at=coalesce(b.resolved_at,now()), updated_at=now()
from pmpd
where b.strategy_id=pmpd.strategy_id
  and b.title in (
      'Build V5 data-quality eligibility and observability layer',
      'Reconcile PMPD-RM-1.0 into a versioned V5 factor roadmap',
      'Freeze 9H outcome and discovery-validation protocol'
  )
  and b.status <> 'complete';

-- 3. Add next 9H execution items.
with pmpd as (
    select strategy_id from public.strategies where strategy_code='PMPD'
),
items(title,description,category,priority,status,origin_phase,blocking_current_phase,why_it_matters) as (
    values
    (
      'Build V5 9H full-universe outcome research dataset',
      'Re-run the certified 112-symbol 2025 structural engine with frozen post-decision outcomes, first-occurrence decision units, quality flags, and deterministic temporal splits.',
      'research_dataset',1,'active','9H',true,
      'Creates the leakage-controlled dataset required before any individual-factor profitability inference.'
    ),
    (
      'Run first 9H data-quality and geometry factor batch',
      'Test observability, price-continuity sensitivity, stack width, pairwise spacing, and PM/AH/PD identity geometry under PMPD_V5_9H_FACTOR_PROTOCOL_V1.',
      'factor_research',2,'ready','9H',true,
      'Starts V5 factor evidence with variables known before or at each decision point and avoids future-event leakage.'
    ),
    (
      'Run 9H progression retention and timing factor batches',
      'After the first batch, test traded-vs-retained state, attempt number, transition timing, and later failure/reclaim factors under the same frozen protocol.',
      'factor_research',3,'backlog','9H',false,
      'Extends individual-factor research without prematurely entering 9I interaction mining.'
    )
)
insert into public.project_backlog (
    strategy_id,title,description,category,priority,status,origin_phase,
    blocking_current_phase,why_it_matters
)
select pmpd.strategy_id,i.title,i.description,i.category,i.priority,i.status,
       i.origin_phase,i.blocking_current_phase,i.why_it_matters
from pmpd cross join items i
where not exists (
    select 1 from public.project_backlog b
    where b.strategy_id=pmpd.strategy_id and b.title=i.title and b.status <> 'complete'
);

-- 4. Record governance decisions.
with pmpd as (
    select strategy_id from public.strategies where strategy_code='PMPD'
),
decisions(title,decision,rationale,evidence,affects_model_version,metadata_json) as (
    values
    (
      'PMPD V5 data-quality eligibility protocol V1 is frozen for 9H',
      'Use PMPD_V5_9H_QUALITY_V1. Preserve all raw rows; primary inference requires complete six-level context and excludes only severe price-scale discontinuities. Sparse PM/AH observability remains eligible and is analyzed as a factor/sensitivity dimension.',
      'Separates obvious corporate-action/scale breaks from legitimate low-observability market structure without outcome-driven deletion.',
      'Alpha 0.2.1 quality audit: 28,000 symbol-days; 26,682 complete; 26,679 primary eligible; 3 severe scale-break days; 20 review-tier continuity days; 6,909 sparse-EH complete days.',
      'V5',
      jsonb_build_object('quality_version','PMPD_V5_9H_QUALITY_V1','severe_days',3,'review_days',20,'sparse_eh_days',6909,'raw_rows_preserved',true)
    ),
    (
      'PMPD V5 factor roadmap V2 preserves legacy roadmap and adds event-native factors',
      'Adopt PMPD-V5-RM-2.0 as the active V5 research roadmap. Preserve all 205 PMPD-RM-1.0 factors historically; reconcile them by disposition and add 48 V5-native factors across quality, geometry, event structure, failure/reclaim, and timing.',
      'V5 changed the research population from V4 signals to Directional Level-Stack Encounters, so signal-centric factors must be carried, reframed, benchmarked, or deferred rather than blindly reused.',
      'Legacy reconciliation: 154 map to 9H, 18 benchmark-only for 9N, 13 interactions defer to 9I, 6 entry/latency concepts defer to 9J, 14 robustness guardrails. Native inventory: 48 factors.',
      'V5',
      jsonb_build_object('roadmap_version','PMPD-V5-RM-2.0','legacy_factor_count',205,'v5_native_factor_count',48,'legacy_rows_overwritten',false)
    ),
    (
      'PMPD V5 9H individual-factor testing protocol V1 is frozen before outcome review',
      'Use first occurrence of each decision type per parent event as the primary unit; evaluate outcomes strictly after the completed decision bar; retain symmetric +0.50/-0.50 favorable-first as primary benchmark; use fixed 2025 discovery and two validation windows; prohibit 9H interaction mining.',
      'Precommitting units, outcomes, temporal splits, cutpoint rules, sample gates, uncertainty reporting, and multiple-comparison control reduces threshold leakage and false discovery.',
      'Protocol PMPD_V5_9H_FACTOR_PROTOCOL_V1.',
      'V5',
      jsonb_build_object(
          'protocol_id','PMPD_V5_9H_FACTOR_PROTOCOL_V1',
          'discovery_end','2025-04-30',
          'validation_a_start','2025-05-01','validation_a_end','2025-08-29',
          'validation_b_start','2025-09-02',
          'primary_favorable_pct',0.50,'primary_adverse_pct',0.50,
          'first_occurrence_per_event_decision_type',true,
          'interaction_mining_allowed',false
      )
    )
)
insert into public.project_decisions (
    strategy_id,title,decision,rationale,evidence,affects_model_version,metadata_json
)
select pmpd.strategy_id,d.title,d.decision,d.rationale,d.evidence,d.affects_model_version,d.metadata_json
from pmpd cross join decisions d
where not exists (
    select 1 from public.project_decisions x
    where x.strategy_id=pmpd.strategy_id and x.title=d.title and x.status='active'
);

-- 5. Update project state / roadmap status.
with pmpd as (
    select strategy_id from public.strategies where strategy_code='PMPD'
)
update public.project_state ps
set
    active_phase_code='9H',
    active_phase_name='Individual Factor Research',
    next_phase_code='9I',
    next_phase_name='Factor Interaction & Archetype Research',
    baseline_model='V4 Forward Validation FINAL',
    baseline_status='FROZEN_BENCHMARK',
    historical_dataset_status='PMPD_112_V1 / 2025 CERTIFIED; V5 ALPHA 0.2.1 STRUCTURAL CERTIFIED; 9H QUALITY/PROTOCOL FROZEN',
    last_decision='9H foundations complete; build full-universe frozen-outcome research dataset before first factor batch.',
    roadmap_version='PMPD-V5-RM-2.0',
    metadata_json=coalesce(ps.metadata_json,'{}'::jsonb) || jsonb_build_object(
        'v5_governance_version','PMPD-V5-GOV-1.2',
        'v5_factor_roadmap_version','PMPD-V5-RM-2.0',
        'v5_current_substep','9H-4A',
        'v5_quality_version','PMPD_V5_9H_QUALITY_V1',
        'v5_factor_protocol','PMPD_V5_9H_FACTOR_PROTOCOL_V1',
        'v5_legacy_factor_count',205,
        'v5_native_factor_count',48,
        'v5_primary_inference_complete_days',26679,
        'v5_severe_scale_days',3,
        'v5_sparse_eh_days',6909,
        'supabase_capacity_status','UPGRADED_NO_CURRENT_DB_LIMITATION',
        'supabase_capacity_is_research_constraint',false
    ),
    updated_at=now()
from pmpd
where ps.strategy_id=pmpd.strategy_id;

-- 6. Validation.
do $$
declare
    v_strategy_id uuid;
    v_native integer;
    v_state integer;
    v_9h text;
begin
    select strategy_id into v_strategy_id from public.strategies where strategy_code='PMPD';

    select count(*) into v_native
    from public.research_factors
    where strategy_id=v_strategy_id
      and factor_code like 'V5%'
      and roadmap_version='PMPD-V5-RM-2.0'
      and timing_type='mixed';
    if v_native < 48 then
        raise exception 'Migration 021: expected at least 48 V5-native factors on PMPD-V5-RM-2.0 with schema-compatible timing_type=mixed, found %.',v_native;
    end if;

    select status into v_9h from public.program_phases
    where strategy_id=v_strategy_id and phase_code='9H';
    if v_9h <> 'active' then
        raise exception 'Migration 021: 9H must remain active; found %.',v_9h;
    end if;

    select count(*) into v_state
    from public.project_state
    where strategy_id=v_strategy_id
      and active_phase_code='9H'
      and next_phase_code='9I'
      and roadmap_version='PMPD-V5-RM-2.0'
      and baseline_status='FROZEN_BENCHMARK';
    if v_state <> 1 then
        raise exception 'Migration 021: project_state validation failed.';
    end if;
end
$$;

commit;

-- 7. Post-migration readout.
with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
select
    ps.active_phase_code, ps.active_phase_name, ps.next_phase_code, ps.next_phase_name,
    ps.roadmap_version, ps.baseline_status, ps.historical_dataset_status, ps.last_decision,
    ps.metadata_json ->> 'v5_current_substep' as current_substep,
    ps.metadata_json ->> 'v5_quality_version' as quality_version,
    ps.metadata_json ->> 'v5_factor_protocol' as factor_protocol
from public.project_state ps join pmpd on pmpd.strategy_id=ps.strategy_id;

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
select family,count(*) as v5_native_factors
from public.research_factors rf join pmpd on pmpd.strategy_id=rf.strategy_id
where rf.factor_code like 'V5%'
group by family order by family;
