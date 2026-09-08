-- Migration 030 — PMPD V5 9J structural architecture results
begin;
with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
insert into public.research_experiments(strategy_id,experiment_code,experiment_name,hypothesis,status,universe,start_date,end_date,n,symbol_count,primary_metric,confidence_level,finding,decision,sql_or_notebook_reference,code_version,model_version,parameters_json,result_json,completed_at)
select pmpd.strategy_id,'PMPD_V5_9J_STRUCTURAL_ARCH_V1','PMPD V5 structural entry/confirmation architecture comparison',
'Pre-existing structural decision points may offer reliability/coverage/delay tradeoffs without factor threshold optimization.','complete','PMPD_112_V1','2025-01-02','2025-12-31',249177,112,'Favorable-first vs adverse-first at symmetric +/-0.50%','95% intervals + symbol-cluster comparisons',
'DP5 completed-bar retention does not improve on DP4 full-stack first clear. Bear DP4 versus first contact is conditionally favorable but Validation B cluster uncertainty includes zero. Reclaim architectures are not stable standalone entries.',
'Keep DP4 full-stack first clear as the structural benchmark; do not require DP5 retention as a default confirmation. Preserve Bear DP4 improvement as conditional architecture evidence. Continue 9J with preregistered VWAP-state enrichment before closure.',
'PMPD_V5_9J_STRUCTURAL_ARCH_RESULTS','PMPD_V5_9J_ENTRY_ARCH_PROTOCOL_V1','V5',
jsonb_build_object('prior_dp_baselines_known_from_9h',true,'production_rule_authorized',false),
jsonb_build_object('dp5_incremental_gain',false,'bear_dp4_vs_dp1','CONDITIONAL','bull_dp4_vs_dp1','UNSTABLE','reclaim_entry','NO_STABLE_EVIDENCE','vwap_enrichment_required',true),now()
from pmpd where not exists(select 1 from public.research_experiments e where e.strategy_id=pmpd.strategy_id and e.experiment_code='PMPD_V5_9J_STRUCTURAL_ARCH_V1');
with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.project_state ps set last_decision='9J structural batch: DP5 retention adds no reliable gain over DP4; Bear DP4 vs contact is conditional; reclaim entries unstable. 9J remains open pending leakage-safe VWAP entry-context enrichment.',
metadata_json=coalesce(ps.metadata_json,'{}'::jsonb)||jsonb_build_object('v5_current_substep','9J-VWAP-ENRICHMENT-DESIGN','v5_9j_structural_batch_status','COMPLETE','v5_9j_dp5_required',false,'v5_9j_bear_dp4_architecture','CONDITIONAL','v5_9j_vwap_enrichment_required',true,'v5_production_rule_authorized',false),updated_at=now()
from pmpd where ps.strategy_id=pmpd.strategy_id;
commit;