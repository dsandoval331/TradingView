-- PM+PD V5 Phase 9K open — 2026-09-08
-- Explicitly authorized by user after 9J closeout.
update program_phases
set status='active',
    started_at=coalesce(started_at,now()),
    notes='ACTIVE. 9K opened by explicit user authorization after certified 9J closeout. Objective: build a reproducible evidence-derived classification/scoring architecture from demonstrated V5 evidence, not inherited weights. Preserve V4 frozen benchmark. 9J conditional/context findings are inputs, not automatically promoted rules. No Pine/production rule authorization in 9K. Candidate model freeze belongs to 9L.',
    updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e'
  and phase_code='9K';

update project_state
set active_phase_code='9K',
    active_phase_name='Evidence-Derived Classification / Scoring',
    next_phase_code='9L',
    next_phase_name='V5 Candidate Model Freeze',
    blocker_count=0,
    last_decision='9K OPENED by explicit user authorization after 9J completion. Begin evidence inventory and scoring/classification architecture design; no inherited weights, no Pine rule authorization, and no 9L freeze yet.',
    metadata_json=coalesce(metadata_json,'{}'::jsonb)||jsonb_build_object(
      'v5_current_phase','9K',
      'v5_9j_status','COMPLETE',
      'v5_9k_status','ACTIVE',
      'v5_9k_authorized',true,
      'pmpd_v5_9j_9k_opened',true,
      'v5_current_substep','9K-1-EVIDENCE-INVENTORY-AND-ELIGIBILITY',
      'v5_9k_production_rule_authorized',false,
      'v5_9l_opened',false
    ),
    updated_at=now()
where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e';
