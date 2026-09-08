-- PM+PD project-management reconciliation backup
-- Strategy: 84fb30c1-7600-49bf-a024-022f0500492e
-- Purpose: preserve legacy 8H history, make PMPD-V5-RM-2.0 / 9A-9P authoritative,
-- and maintain one PMPD program with V4 frozen benchmark + V5 active research track.

begin;

-- Legacy 8H roadmap: preserve rows but explicitly mark superseded/unentered work.
update public.program_phases
set status='cancelled',
    notes=case
      when phase_code='8H-6' then
        'Legacy PMPD 8H roadmap was superseded while this phase was active by the V5 soft-reset roadmap beginning at 9A. Substantial historical-engine/data work is preserved in project_decisions, including PMPD_112_V1 x 2025 RESEARCH_READY certification. This phase was not advanced to 8H-7 under the legacy roadmap.'
      else
        'Legacy PMPD 8H roadmap phase preserved for provenance but cancelled/superseded before entry by the V5 9A-9P roadmap. Not completed and not part of current progression.'
    end,
    updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e'
  and phase_code in ('8H-6','8H-7','8H-8','8H-9','8H-10','8H-11','8H-12','8H-13','8H-14','8H-15');

-- V5 current phase chronology.
update public.program_phases
set status='complete',
    completed_at='2026-09-05 17:37:39.795267+00'::timestamptz,
    notes='COMPLETE. 9H individual-factor research closed. 48 V5-native factors and 205 legacy factors are accounted for; zero final-SUPPORTED individual scopes; four CONDITIONAL scopes carried forward as context. No production rule authorized.',
    updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e' and phase_code='9H';

update public.program_phases
set status='complete',
    started_at=coalesce(started_at,'2026-09-05 17:37:39.795267+00'::timestamptz),
    completed_at='2026-09-05 17:45:58.640955+00'::timestamptz,
    notes='Closed with NO_REPRODUCIBLE_INCREMENTAL_INTERACTION. No interaction-derived production rule authorized.',
    updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e' and phase_code='9I';

update public.program_phases
set status='active',
    started_at=coalesce(started_at,'2026-09-05 17:45:58.640955+00'::timestamptz),
    completed_at=null,
    notes='ACTIVE authoritative V5 phase. Current substep: 9J-VWAP-EVENT-PATH-V2, DP1-anchored event-specific VWAP path research. Structural entry/confirmation work and VWAP V1 snapshot work are complete; V2 integrity/analysis is required before 9J closeout. No production rule authorized. 9K must not open until 9J is explicitly closed.',
    updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e' and phase_code='9J';

-- Resolved backlog rows no longer block the current phase.
update public.project_backlog
set blocking_current_phase=false, updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e'
  and status in ('complete','cancelled','rejected')
  and blocking_current_phase=true;

-- One PMPD strategy, two model tracks.
update public.strategies
set description='PM+PD research program. V4 is the frozen benchmark/forward-validation implementation; V5 is the active event-based research successor under the 9A-9P roadmap. Both are model tracks within one PMPD strategy/program, not competing current project states.',
    metadata_json=coalesce(metadata_json,'{}'::jsonb) || jsonb_build_object(
      'governance_model','ONE_STRATEGY_MULTIPLE_MODEL_TRACKS',
      'v4_track_status','FROZEN_BENCHMARK_FORWARD_VALIDATION',
      'v5_track_status','ACTIVE_RESEARCH',
      'legacy_roadmap_version','PMPD-RM-1.0',
      'active_roadmap_version','PMPD-V5-RM-2.0',
      'active_phase','9J',
      'next_phase','9K'
    ),
    updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';

update public.project_state
set active_phase_code='9J',
    active_phase_name='Alternative Entry / Confirmation Architectures',
    next_phase_code='9K',
    next_phase_name='Evidence-Derived Classification / Scoring',
    blocker_count=(
      select count(*)::int
      from public.project_backlog b
      where b.strategy_id=project_state.strategy_id
        and b.status in ('backlog','ready','active','blocked')
        and b.blocking_current_phase=true
    ),
    baseline_model='V4 Forward Validation FINAL',
    baseline_status='FROZEN_BENCHMARK',
    historical_dataset_status='PMPD_112_V1 / 2025 CERTIFIED; V5 9H COMPLETE; 9I COMPLETE; 9J ACTIVE',
    roadmap_version='PMPD-V5-RM-2.0',
    last_decision='PM+PD project management reconciled: one PMPD program with V4 frozen as benchmark and V5 as the active research track. Legacy 8H roadmap is preserved as superseded; PMPD-V5-RM-2.0 / phases 9A-9P are authoritative. Current phase remains 9J at VWAP Event-Path V2; 9K is next but not opened.',
    metadata_json=(coalesce(metadata_json,'{}'::jsonb) - 'roadmap_version' - 'factor_roadmap_note') ||
      jsonb_build_object(
        'roadmap_version','PMPD-V5-RM-2.0',
        'active_roadmap_version','PMPD-V5-RM-2.0',
        'legacy_roadmap_version','PMPD-RM-1.0',
        'legacy_8h_roadmap_status','SUPERSEDED_PRESERVED',
        'v5_phase_roadmap','9A-9P',
        'v5_current_phase','9J',
        'v5_9h_status','COMPLETE',
        'v5_9i_status','COMPLETE',
        'v5_9j_status','ACTIVE',
        'factor_roadmap_note','PMPD-RM-1.0 preserved as legacy evidence/factor roadmap; PMPD-V5-RM-2.0 is the authoritative active V5 roadmap with explicit 205-to-48 reconciliation ledger.',
        'governance_model','ONE_STRATEGY_MULTIPLE_MODEL_TRACKS',
        'v4_track_status','FROZEN_BENCHMARK_FORWARD_VALIDATION',
        'v5_track_status','ACTIVE_RESEARCH',
        'historical_architecture_status','RESEARCH_READY',
        'controlled_2025_symbols_complete',112,
        'controlled_2025_symbols_total',112,
        'controlled_2025_percent_complete',100,
        'controlled_acquisition_sets_complete',4
      ),
    updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';

-- Idempotent governance decision.
insert into public.project_decisions (
  decision_id,strategy_id,decision_date,title,decision,rationale,evidence,
  affects_model_version,status,metadata_json
)
select gen_random_uuid(),
       '84fb30c1-7600-49bf-a024-022f0500492e'::uuid,
       now(),
       'PM+PD roadmap and model-track governance reconciled',
       'Manage PM+PD as one strategy/program with distinct model tracks: V4 remains the frozen benchmark/forward-validation implementation; V5 is the active event-based research successor. Preserve PMPD-RM-1.0 and the 8H phase history as superseded provenance. PMPD-V5-RM-2.0 and phases 9A-9P are authoritative for current progression. Current phase is 9J; 9K remains unopened.',
       'The project-management tables had stale simultaneous active states that contradicted project_state and documented 9H/9I closeout decisions. Separating model tracks within one PMPD strategy preserves benchmark continuity and research provenance without creating competing sources of truth.',
       'Conversation-authoritative PMPD V5 chronology; 9H/9I closeout decisions; project_state at 9J; PMPD-V5-RM-2.0 adoption; PMPD-RM-1.0 preservation.',
       null,
       'active',
       jsonb_build_object(
         'governance_model','ONE_STRATEGY_MULTIPLE_MODEL_TRACKS',
         'v4_status','FROZEN_BENCHMARK_FORWARD_VALIDATION',
         'v5_status','ACTIVE_RESEARCH',
         'legacy_roadmap','PMPD-RM-1.0',
         'legacy_phase_roadmap','8H-1..8H-15',
         'legacy_roadmap_status','SUPERSEDED_PRESERVED',
         'active_roadmap','PMPD-V5-RM-2.0',
         'active_phase_roadmap','9A-9P',
         'current_phase','9J',
         'next_phase','9K',
         'production_rule_authorized',false
       )
where not exists (
  select 1 from public.project_decisions
  where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e'
    and title='PM+PD roadmap and model-track governance reconciled'
);

commit;
