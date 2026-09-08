-- Migration 026 — PMPD V5 close 9H and authorize 9I
begin;

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
insert into public.research_experiments(
 strategy_id,experiment_code,experiment_name,hypothesis,status,universe,start_date,end_date,n,symbol_count,
 primary_metric,confidence_level,finding,decision,sql_or_notebook_reference,code_version,model_version,
 parameters_json,result_json,completed_at
)
select pmpd.strategy_id,
 'PMPD_V5_9H_B4_FINAL_ADJUDICATION_V1',
 'PMPD V5 9H Batch 4 final remaining-factor adjudication',
 'Remaining V5-native factors must survive the same frozen 9H discovery/FDR/validation/cluster gate before promotion.',
 'complete','PMPD_112_V1','2025-01-02','2025-12-31',249177,112,
 'Favorable-first vs adverse-first at symmetric +/-0.50%',
 '95% + family BH FDR + symbol-cluster validation',
 'Batch 4 produced no new SUPPORTED or CONDITIONAL factors. V5S01 Bear DP10 MULTI_AH_PD is suggestive only; V5L11/V5L12/V5S02 are unstable; V5L02/V5S13/V5S14/V5R08 show no stable evidence.',
 'Close 9H. Freeze four previously identified CONDITIONAL scopes as the 9I interaction candidate pool; no production rule is authorized.',
 'PMPD_V5_9H_BATCH_4_FINAL',
 'PMPD_V5_9H_FACTOR_PROTOCOL_V1','V5',
 jsonb_build_object(
   'enrichment_version','PMPD_V5_9H_ENRICHMENT_V1',
   'enrichment_fingerprint','a43e799ae77fa60a30685cefd6cb9b0a861316311b73ce91ee1dd0884938e002',
   'rows',450491,'primary_rows',266076,'resolved_primary_rows',249177,
   'join_unmatched',0,'duplicate_decision_ids',0
 ),
 jsonb_build_object(
   'new_supported',0,'new_conditional',0,'new_suggestive',1,
   'final_supported_scopes',0,'final_conditional_scopes_for_9i',4,
   'native_48_accounted_for',true,'legacy_205_accounted_for',true
 ),
 now()
from pmpd
where not exists (
 select 1 from public.research_experiments e
 where e.strategy_id=pmpd.strategy_id and e.experiment_code='PMPD_V5_9H_B4_FINAL_ADJUDICATION_V1'
);

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.research_factors f
set status='research_only', predictive_strength='no_evidence',
    finding='9H final: ATR-normalized stack width did not show a stable discovery/validation relationship under the frozen evidence gate.',
    production_status='not_promoted', tested_n=249177, tested_symbols=112, updated_at=now()
from pmpd where f.strategy_id=pmpd.strategy_id and f.factor_code='V5L02';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.research_factors f
set status='research_only', predictive_strength='unstable',
    finding='9H final: RTH-open pre-cleared level count showed discovery effects that failed family FDR and reversed across validation windows.',
    production_status='not_promoted', tested_n=249177, tested_symbols=112, updated_at=now()
from pmpd where f.strategy_id=pmpd.strategy_id and f.factor_code='V5L11';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.research_factors f
set status='research_only', predictive_strength='unstable',
    finding='9H final: RTH-open location relative to stack showed discovery effects that failed family FDR and reversed across validation windows.',
    production_status='not_promoted', tested_n=249177, tested_symbols=112, updated_at=now()
from pmpd where f.strategy_id=pmpd.strategy_id and f.factor_code='V5L12';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.research_factors f
set status='research_only', predictive_strength='suggestive',
    finding='9H final: Bear DP10 first-contact identity MULTI_AH_PD retained a negative sign across all three temporal windows, but family FDR was weak and both validation symbol-cluster 95% intervals crossed zero. Suggestive only.',
    production_status='not_promoted', tested_n=249177, tested_symbols=112, updated_at=now()
from pmpd where f.strategy_id=pmpd.strategy_id and f.factor_code='V5S01';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.research_factors f
set status='research_only', predictive_strength='unstable',
    finding='9H final: first-cleared level identity did not replicate stably across both validation windows.',
    production_status='not_promoted', tested_n=249177, tested_symbols=112, updated_at=now()
from pmpd where f.strategy_id=pmpd.strategy_id and f.factor_code='V5S02';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.research_factors f
set status='research_only', predictive_strength='no_evidence',
    finding='9H final: contemporaneous directional recross count did not survive the frozen discovery/FDR/validation gate.',
    production_status='not_promoted', tested_n=249177, tested_symbols=112, updated_at=now()
from pmpd where f.strategy_id=pmpd.strategy_id and f.factor_code='V5S13';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.research_factors f
set status='research_only', predictive_strength='no_evidence',
    finding='9H final: contemporaneous structural progression path signature did not show stable evidence after controlling rare paths and the frozen evidence gate.',
    production_status='not_promoted', tested_n=249177, tested_symbols=112, updated_at=now()
from pmpd where f.strategy_id=pmpd.strategy_id and f.factor_code='V5S14';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.research_factors f
set status='research_only', predictive_strength='no_evidence',
    finding='9H final: warning-persistence elapsed time and warning-transition count at DP10-DP12 did not show a stable discovery/validation relationship.',
    production_status='not_promoted', tested_n=249177, tested_symbols=112, updated_at=now()
from pmpd where f.strategy_id=pmpd.strategy_id and f.factor_code='V5R08';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.project_backlog b
set status='complete', resolved_at=coalesce(resolved_at,now()), updated_at=now()
from pmpd
where b.strategy_id=pmpd.strategy_id
  and b.title='Enrich 9H event transition and RTH-open dataset for remaining V5 factors'
  and b.status <> 'complete';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
insert into public.project_decisions(
 strategy_id,title,decision,rationale,evidence,affects_model_version,metadata_json
)
select pmpd.strategy_id,
 'PMPD V5 9H individual-factor research closed',
 'Close 9H and authorize 9I Factor Interaction & Archetype Research. Freeze four CONDITIONAL scopes as the initial 9I candidate pool; zero individual scopes are final-SUPPORTED.',
 'All 48 V5-native factors are accounted for and the remaining eight researchable factors were adjudicated using the preregistered enrichment definitions. The Batch-4 package matched the parent dataset 1:1 with no duplicate IDs, no unmatched decisions, and no audited temporal-order defects.',
 'PMPD_V5_9H_BATCH4_INTEGRITY_AUDIT_V1; PMPD_V5_9H_BATCH4_FACTOR_ADJUDICATION_V1; PMPD_V5_9I_CANDIDATE_POOL_FROM_9H_V1.',
 'V5',
 jsonb_build_object(
   '9h_status','COMPLETE',
   '9i_authorized',true,
   'final_supported_scopes',0,
   'conditional_scopes_for_9i',4,
   'legacy_205_accounted_for',true,
   'native_48_accounted_for',true,
   'production_rule_authorized',false
 )
from pmpd
where not exists (
 select 1 from public.project_decisions d
 where d.strategy_id=pmpd.strategy_id and d.title='PMPD V5 9H individual-factor research closed' and d.status='active'
);

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.project_state ps
set active_phase_code='9I',
    active_phase_name='Factor Interaction & Archetype Research',
    next_phase_code='9J',
    next_phase_name='Alternative Entry / Confirmation Architectures',
    historical_dataset_status='PMPD_112_V1 / 2025 CERTIFIED; V5 9H COMPLETE; 9I AUTHORIZED',
    last_decision='9H complete: zero final-SUPPORTED individual scopes; four CONDITIONAL scopes frozen for conservative 9I interaction/archetype research.',
    metadata_json=coalesce(ps.metadata_json,'{}'::jsonb) || jsonb_build_object(
      'v5_current_substep','9I-PREREGISTRATION',
      'v5_9h_status','COMPLETE',
      'v5_9h_batch4_status','COMPLETE',
      'v5_9h_final_supported_count',0,
      'v5_9h_conditional_scope_count',4,
      'v5_9i_candidate_pool_status','FROZEN_FROM_9H',
      'v5_9i_authorized',true,
      'v5_production_rule_authorized',false
    ),
    updated_at=now()
from pmpd
where ps.strategy_id=pmpd.strategy_id;

commit;
