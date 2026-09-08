-- Migration 027 — PMPD V5 9I interaction/archetype preregistration
begin;

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
insert into public.research_experiments(
 strategy_id,experiment_code,experiment_name,hypothesis,status,universe,start_date,end_date,
 primary_metric,confidence_level,sql_or_notebook_reference,code_version,model_version,
 parameters_json,result_json
)
select pmpd.strategy_id,
 'PMPD_V5_9I_PREREGISTRATION_V1',
 'PMPD V5 9I factor interaction and archetype preregistration',
 'A narrow set of interactions among 9H-preserved CONDITIONAL scopes may reveal reproducible incremental structure without exhaustive interaction mining.',
 'ready','PMPD_112_V1','2025-01-02','2025-12-31',
 'Favorable-first vs adverse-first at symmetric +/-0.50%',
 'Discovery family BH FDR + Validation A/B + symbol-cluster robustness',
 'PMPD_V5_9I_INTERACTION_PROTOCOL_V1.json',
 'PMPD_V5_9I_INTERACTION_PROTOCOL_V1','V5',
 jsonb_build_object(
   'candidate_scope_count',4,
   'primary_same_dp_interaction','BULL_DP4_ALIGNED_GAP_X_TIME',
   'sequential_archetypes',jsonb_build_array(
      'BULL_DP3_SCALE_TO_DP4_GAP',
      'BULL_DP3_SCALE_TO_DP4_TIME',
      'BULL_DP3_SCALE_TO_DP4_GAP_X_TIME'
   ),
   'bear_policy','characterization_only_without_adding_weak_factor',
   'threshold_policy','DISCOVERY_ONLY',
   'exhaustive_48_factor_search',false,
   'production_rule_authorized',false,
   'frozen_before_results',true
 ),
 jsonb_build_object('status','PREREGISTERED_NO_INTERACTION_RESULTS_YET')
from pmpd
where not exists (
 select 1 from public.research_experiments e
 where e.strategy_id=pmpd.strategy_id
   and e.experiment_code='PMPD_V5_9I_PREREGISTRATION_V1'
);

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
insert into public.project_decisions(
 strategy_id,title,decision,rationale,evidence,affects_model_version,metadata_json
)
select pmpd.strategy_id,
 'PMPD V5 9I interaction search space frozen',
 'Restrict initial 9I testing to Bull DP4 aligned-gap x time, preregistered Bull DP3-to-DP4 sequential archetypes, and Bear DP4 aligned-gap characterization. Do not search all 48 factors or add weak factors merely to create interactions.',
 '9H produced zero final-SUPPORTED individual scopes and four CONDITIONAL scopes. A narrow preregistered interaction space protects against combinatorial overfitting while still testing whether the surviving evidence becomes incrementally useful in context.',
 'PMPD_V5_9I_INTERACTION_PROTOCOL_V1.json',
 'V5',
 jsonb_build_object(
   'protocol_id','PMPD_V5_9I_INTERACTION_PROTOCOL_V1',
   'candidate_scope_count',4,
   'interaction_space_frozen',true,
   'production_rule_authorized',false
 )
from pmpd
where not exists (
 select 1 from public.project_decisions d
 where d.strategy_id=pmpd.strategy_id
   and d.title='PMPD V5 9I interaction search space frozen'
   and d.status='active'
);

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.project_state ps
set last_decision='9I preregistered: narrow interaction/archetype search space frozen before results; Bull DP4 gap x time is primary interaction.',
    metadata_json=coalesce(ps.metadata_json,'{}'::jsonb) || jsonb_build_object(
      'v5_current_substep','9I-2-BULL-DP4-INTERACTION',
      'v5_9i_protocol_id','PMPD_V5_9I_INTERACTION_PROTOCOL_V1',
      'v5_9i_preregistration_status','COMPLETE',
      'v5_9i_interaction_space_frozen',true,
      'v5_production_rule_authorized',false
    ),
    updated_at=now()
from pmpd
where ps.strategy_id=pmpd.strategy_id;

commit;
