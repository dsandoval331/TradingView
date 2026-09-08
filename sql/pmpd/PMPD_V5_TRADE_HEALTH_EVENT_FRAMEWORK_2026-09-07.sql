-- PM+PD V5 Trade Health / Event Framework preservation
-- Idempotent backup corresponding to 2026-09-07 Supabase updates.

insert into project_backlog
(strategy_id,title,description,category,priority,status,origin_phase,blocking_current_phase,why_it_matters,created_at,updated_at)
select
'84fb30c1-7600-49bf-a024-022f0500492e',
'Design and integrate PM+PD V5 Trade Health / Event Framework',
'Before 9P Pine implementation, design a modular post-actionable-signal Trade Health/Event Engine for V5 research: timestamped event log; compact candle markers; balanced SUPPORT and deterioration events; provisional severity; VWAP interaction state machine; failed continuation/structure; IFT 1m/3m/5m/10m; momentum and expected-response failure; recovery/failed recovery; VWAP/structural stop research; evolving health state; research/debug measurements; export compatibility with Trade Review Tool and future Real-Time Trade Advisor. Preserve frozen V4. Candidate events are research features, not proven exit rules or frozen thresholds.',
'trade_health_event_framework',1,'backlog','9P',false,
'Ensures candidate post-signal health events are implemented prospectively in the new V5 indicator and share definitions with Trade Review/Advisor, without contaminating current 9J entry-architecture research or altering frozen V4.',
now(),now()
where not exists (
 select 1 from project_backlog
 where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e'
 and title='Design and integrate PM+PD V5 Trade Health / Event Framework'
);

insert into project_decisions
(strategy_id,decision_date,title,decision,rationale,evidence,affects_model_version,status,metadata_json)
select
'84fb30c1-7600-49bf-a024-022f0500492e',now(),
'PM+PD V5 Trade Health / Event Framework preserved before Pine generation',
'Add the Trade Health/Event framework to the V5 plan before Pine generation. Keep frozen V4 unchanged. Treat event definitions, severities, thresholds, and health transitions as modular research features until validated; include both supportive and contradictory evidence; keep Signal Quality separate from post-signal Trade Health; design common event semantics for Pine, Trade Review, and future Real-Time Advisor.',
'The framework arose from actual-trade review and should be prospectively measurable, but a single example cannot establish thresholds or exit rules. Current 9J remains entry/confirmation research; implementation belongs before/within 9P after research architecture is reviewed.',
'Trade Analysis: Review Tool design transfer; existing decision Separate Signal Quality and Trade Health; PMPD-V5-RM-2.0 event-native architecture.',
'V5','active',
jsonb_build_object(
 'frozen_v4_unchanged',true,
 'production_exit_rule_authorized',false,
 'pine_generation_blocked_until_design_review',true,
 'event_families',jsonb_build_array(
  'signal_entry_context','vwap_interaction','price_structure_continuation',
  'initial_follow_through','momentum_expected_response','recovery_failed_recovery',
  'risk_stop_management','trade_health_transition','supportive_evidence'
 ),
 'shared_consumers',jsonb_build_array('Pine indicator','Trade Review Tool','Real-Time Trade Advisor')
)
where not exists (
 select 1 from project_decisions
 where strategy_id='84fb30c1-7600-49bf-a024-022f0500492e'
 and title='PM+PD V5 Trade Health / Event Framework preserved before Pine generation'
);
