-- Migration 024 — PMPD V5 9H strict adjudication and coverage audit
begin;

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.project_backlog b
set status='complete', resolved_at=coalesce(resolved_at,now()), updated_at=now()
from pmpd
where b.strategy_id=pmpd.strategy_id
  and b.title='Run 9H Batch 2 progression retention timing and directional-context factors'
  and b.status <> 'complete';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.project_backlog b
set status='complete', resolved_at=coalesce(resolved_at,now()), updated_at=now()
from pmpd
where b.strategy_id=pmpd.strategy_id
  and b.title='Run 9H progression retention and timing factor batches'
  and b.status <> 'complete';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD'),
items(title,description,category,priority,status,origin_phase,blocking_current_phase,why_it_matters) as (
 values (
  'Enrich 9H event transition and RTH-open dataset for remaining V5 factors',
  'Add ATR-normalized stack width, RTH-open stack context, first-contact/first-clear identity, recross/path signature, and warning-persistence fields/transition export, then rerun the frozen 9H adjudication protocol.',
  'research_dataset',1,'active','9H',true,
  'The 48-factor coverage audit found remaining V5-native factors that cannot be adjudicated from the current research export without richer event/transition context.'
 )
)
insert into public.project_backlog(strategy_id,title,description,category,priority,status,origin_phase,blocking_current_phase,why_it_matters)
select pmpd.strategy_id,i.title,i.description,i.category,i.priority,i.status,i.origin_phase,i.blocking_current_phase,i.why_it_matters
from pmpd cross join items i
where not exists (
 select 1 from public.project_backlog b
 where b.strategy_id=pmpd.strategy_id and b.title=i.title and b.status <> 'complete'
);

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
insert into public.research_experiments(
 strategy_id,experiment_code,experiment_name,hypothesis,status,universe,start_date,end_date,n,symbol_count,
 primary_metric,confidence_level,finding,decision,sql_or_notebook_reference,code_version,model_version,parameters_json,result_json,completed_at
)
select pmpd.strategy_id,
 'PMPD_V5_9H_B3_STRICT_ADJUDICATION_V1',
 'PMPD V5 9H Batch 3 strict factor adjudication',
 'Individual-factor candidates must survive discovery family-level FDR and both validation windows with symbol-cluster uncertainty before receiving SUPPORTED status.',
 'complete','PMPD_112_V1','2025-01-02','2025-12-31',249177,112,
 'Favorable-first vs adverse-first at symmetric +/-0.50%',
 '95% + family BH FDR + symbol-cluster bootstrap',
 'No factor receives final SUPPORTED status under the full frozen gate. V5Q07 bullish DP3, direction-normalized overnight gap at DP4, and bullish DP4 time-of-day remain CONDITIONAL. Preliminary R05 elapsed evidence was invalidated after enforcing temporal order.',
 'Keep 9H active. Do not start 9I until remaining data-enrichment factors are adjudicated.',
 'PMPD_V5_9H_BATCH_3_ADJUDICATION',
 'PMPD_V5_9H_FACTOR_PROTOCOL_V1',
 'V5',
 jsonb_build_object('protocol_id','PMPD_V5_9H_FACTOR_PROTOCOL_V1','strict_supported_count',0,'conditional_count',4,'suggestive_count',1),
 jsonb_build_object('legacy_factors_accounted_for',205,'native_factor_count',48,'direct_tested_representations',31,'needs_enrichment',8,'production_thresholds_authorized',false),
 now()
from pmpd
where not exists (
 select 1 from public.research_experiments e
 where e.strategy_id=pmpd.strategy_id and e.experiment_code='PMPD_V5_9H_B3_STRICT_ADJUDICATION_V1'
);

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.research_factors f
set status='research_only',
    finding='Conditional: bullish DP3 shows stable negative association with six-level scale ratio across Discovery/Validation A/Validation B, but final family-level discovery FDR is 0.0625 and therefore misses the frozen 0.05 SUPPORTED gate.',
    predictive_strength='conditional',
    tested_n=249177,
    tested_symbols=112,
    production_status='not_promoted',
    updated_at=now()
from pmpd
where f.strategy_id=pmpd.strategy_id and f.factor_code='V5Q07';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.research_factors f
set status='research_only',
    finding='Direction-normalized overnight gap is a strong conditional representation at DP4 in both directions: validation replication is positive and cluster-robust, but Discovery/family-FDR does not pass the frozen final gate.',
    predictive_strength='conditional',
    tested_n=249177,
    tested_symbols=112,
    production_status='not_promoted',
    updated_at=now()
from pmpd
where f.strategy_id=pmpd.strategy_id and f.factor_code='V5Q08';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.research_factors f
set status='research_only',
    finding='Earlier bullish DP4 decisions replicate better in both validation windows with symbol-cluster support, but Discovery/family-FDR does not pass the frozen final gate. Bullish DP5 remains suggestive.',
    predictive_strength='conditional',
    tested_n=249177,
    tested_symbols=112,
    production_status='not_promoted',
    updated_at=now()
from pmpd
where f.strategy_id=pmpd.strategy_id and f.factor_code='V5T02';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.research_factors f
set status='research_only',
    finding='Retention-to-loss elapsed time must only be evaluated when loss occurs after retention. A preliminary exploratory result admitted negative elapsed values and was invalidated. Corrected temporally ordered tests do not support promotion.',
    predictive_strength='no_stable_evidence_yet',
    tested_n=29801,
    tested_symbols=112,
    production_status='not_promoted',
    updated_at=now()
from pmpd
where f.strategy_id=pmpd.strategy_id and f.factor_code='V5R05';

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD'),
d(title,decision,rationale,evidence,affects_model_version,metadata_json) as (
 values (
  'PMPD V5 9H strict adjudication supersedes preliminary screening labels',
  'Treat Batch 1/2 SUPPORTED wording as preliminary screening only. Under the frozen final family-FDR plus symbol-cluster gate, no individual factor is yet final-SUPPORTED. Preserve V5Q07 bullish DP3, direction-normalized gap DP4, and bullish DP4 time-of-day as CONDITIONAL candidates. Keep 9H open for remaining factor-data enrichment.',
  'Final adjudication applies stricter multiplicity, cluster, and temporal-order checks than the earlier screens. It also detected and corrected an invalid negative elapsed-time construction in exploratory R05 analysis.',
  'PMPD_V5_9H_STRICT_ADJUDICATION_LEDGER_V1; PMPD_V5_48_FACTOR_COVERAGE_AUDIT_V1; PMPD_V5_9H_TEMPORAL_ORDER_CORRECTIONS_V1.',
  'V5',
  jsonb_build_object('final_supported_count',0,'conditional_count',4,'suggestive_count',1,'legacy_factors_accounted_for',205,'native_factors',48,'9i_authorized',false)
 )
)
insert into public.project_decisions(strategy_id,title,decision,rationale,evidence,affects_model_version,metadata_json)
select pmpd.strategy_id,d.title,d.decision,d.rationale,d.evidence,d.affects_model_version,d.metadata_json
from pmpd cross join d
where not exists (
 select 1 from public.project_decisions x
 where x.strategy_id=pmpd.strategy_id and x.title=d.title and x.status='active'
);

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
update public.project_state ps
set historical_dataset_status='PMPD_112_V1 / 2025 CERTIFIED; V5 9H OUTCOME DATASET V1 CERTIFIED; STRICT ADJUDICATION COMPLETE; ENRICHMENT ACTIVE',
    last_decision='9H strict adjudication found zero final-SUPPORTED factors under full gate; four CONDITIONAL candidates retained. 9H remains active pending enrichment of remaining V5-native factors.',
    metadata_json=coalesce(ps.metadata_json,'{}'::jsonb) || jsonb_build_object(
      'v5_current_substep','9H-BATCH-4-ENRICHMENT',
      'v5_9h_batch3_status','COMPLETE',
      'v5_9h_final_supported_count',0,
      'v5_9h_conditional_count',4,
      'v5_legacy_205_reconciliation_status','CLOSED_ACCOUNTED_FOR',
      'v5_native_factor_coverage_audit_status','COMPLETE',
      'v5_9i_authorized',false
    ),
    updated_at=now()
from pmpd
where ps.strategy_id=pmpd.strategy_id;

commit;
