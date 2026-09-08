-- Migration 025 — PMPD V5 9H Batch 4 enrichment pre-registration
-- This is a DATA/GOVERNANCE migration only; it creates no new database schema.
begin;

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
insert into public.research_experiments(
 strategy_id,experiment_code,experiment_name,hypothesis,status,universe,start_date,end_date,
 primary_metric,confidence_level,sql_or_notebook_reference,code_version,model_version,
 parameters_json,result_json
)
select
 pmpd.strategy_id,
 'PMPD_V5_9H_B4_ENRICHMENT_V1',
 'PMPD V5 9H Batch 4 remaining-factor enrichment',
 'Remaining V5-native individual factors must be measured using contemporaneously known RTH-open, ATR, identity, recross, path, and warning-persistence fields without inventing intrabar order or leaking future event state.',
 'ready','PMPD_112_V1','2025-01-02','2025-12-31',
 'Favorable-first vs adverse-first at symmetric +/-0.50%',
 'Frozen 9H protocol: family BH FDR + 95% symbol-cluster validation',
 'PMPD_V5_9H_BATCH4_ENRICHMENT_SPEC_V1.json',
 'PMPD_V5_9H_ENRICHMENT_V1','V5',
 jsonb_build_object(
   'enrichment_version','PMPD_V5_9H_ENRICHMENT_V1',
   'parent_dataset_version','PMPD_V5_9H_RESEARCH_DATASET_V1',
   'atr_definition','RTH-local completed 1m Wilder ATR14; resets daily; min_periods=14',
   'multi_level_intrabar_policy','MULTI_*; no invented ordering',
   'recross_definition','bit flips beyond each identity initial flip through DP timestamp',
   'warning_persistence_definition','elapsed time/transitions since most recent 111->non111 through DP timestamp',
   'frozen_before_results',true
 ),
 jsonb_build_object('status','AWAITING_LOCAL_ENRICHMENT_RUN')
from pmpd
where not exists (
 select 1 from public.research_experiments e
 where e.strategy_id=pmpd.strategy_id and e.experiment_code='PMPD_V5_9H_B4_ENRICHMENT_V1'
);

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.project_state ps
set last_decision='9H Batch 4 enrichment definitions frozen before results; local full-universe enrichment run required before remaining-factor adjudication.',
    metadata_json=coalesce(ps.metadata_json,'{}'::jsonb) || jsonb_build_object(
      'v5_current_substep','9H-BATCH-4-ENRICHMENT-RUN',
      'v5_9h_batch4_protocol_status','PREREGISTERED',
      'v5_9h_batch4_enrichment_version','PMPD_V5_9H_ENRICHMENT_V1',
      'v5_9i_authorized',false
    ),
    updated_at=now()
from pmpd
where ps.strategy_id=pmpd.strategy_id;

commit;
