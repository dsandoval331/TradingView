-- PMPD V5 Migration 022 — 9H Dataset Certification + Batch 1 Evidence
begin;

with pmpd as (
  select strategy_id from public.strategies where strategy_code='PMPD'
)
update public.project_backlog b
set status='complete',
    resolved_at=coalesce(b.resolved_at,now()),
    updated_at=now()
from pmpd
where b.strategy_id=pmpd.strategy_id
  and b.title='Build V5 9H full-universe outcome research dataset'
  and b.status <> 'complete';

with pmpd as (
  select strategy_id from public.strategies where strategy_code='PMPD'
)
update public.project_backlog b
set status='complete',
    resolved_at=coalesce(b.resolved_at,now()),
    updated_at=now()
from pmpd
where b.strategy_id=pmpd.strategy_id
  and b.title='Run first 9H data-quality and geometry factor batch'
  and b.status <> 'complete';

with pmpd as (
  select strategy_id from public.strategies where strategy_code='PMPD'
),
items(title,description,category,priority,status,origin_phase,blocking_current_phase,why_it_matters) as (
 values
 (
  'Run 9H Batch 2 progression retention timing and directional-context factors',
  'Test contemporaneously known progression/retention state, attempt number, time-of-day, level identity/order, and a pre-registered direction-normalized overnight-gap representation. Keep failure/reclaim decision points separate and preserve discovery/validation rules.',
  'factor_research',1,'active','9H',true,
  'Extends replicated Batch 1 evidence without entering 9I interaction mining.'
 )
)
insert into public.project_backlog(
 strategy_id,title,description,category,priority,status,origin_phase,blocking_current_phase,why_it_matters
)
select pmpd.strategy_id,i.title,i.description,i.category,i.priority,i.status,i.origin_phase,i.blocking_current_phase,i.why_it_matters
from pmpd cross join items i
where not exists (
 select 1 from public.project_backlog b
 where b.strategy_id=pmpd.strategy_id and b.title=i.title and b.status <> 'complete'
);

with pmpd as (
 select strategy_id from public.strategies where strategy_code='PMPD'
),
decisions(title,decision,rationale,evidence,affects_model_version,metadata_json) as (
 values
 (
  'PMPD V5 9H outcome research dataset V1 certified',
  'Accept PMPD_V5_9H_RESEARCH_DATASET_V1 for 9H individual-factor research.',
  'The full 112-symbol run completed with frozen protocol/quality versions, deterministic fingerprints, 266,057 primary-inference-eligible decision units, 249,177 resolved primary outcomes, and no duplicate decision IDs.',
  'Run fingerprint 5c085460e9d7a4367ca4bc40e5c71374e4634ecccd74de93ec26ba7c3f9e7fbb; decision fingerprint 989d6583c5aee0f2f6589c5d58edf6d2b556939a5eec18dfda056ba83af7ac2b.',
  'V5',
  jsonb_build_object(
   'dataset_version','PMPD_V5_9H_RESEARCH_DATASET_V1',
   'run_fingerprint','5c085460e9d7a4367ca4bc40e5c71374e4634ecccd74de93ec26ba7c3f9e7fbb',
   'decision_fingerprint','989d6583c5aee0f2f6589c5d58edf6d2b556939a5eec18dfda056ba83af7ac2b',
   'decision_rows',450491,'primary_eligible_rows',266057,'resolved_primary_rows',249177,'symbols',112
  )
 ),
 (
  'PMPD V5 9H Batch 1 produces first replicated individual-factor evidence',
  'Retain four findings as SUPPORTED research candidates: bullish DP4 overnight gap, bullish DP5 overnight gap, bullish DP4 time-from-open, and bullish DP3 six-level scale ratio. Keep related bearish/observability findings SUGGESTIVE. Do not convert discovery quartiles into production thresholds.',
  'Each supported finding preserved direction across Discovery, Validation A, and Validation B and cleared the symbol-cluster uncertainty gate in both validation windows. 9H remains individual-factor research; no interaction mining or production rule promotion is authorized.',
  'PMPD_V5_9H_BATCH_1_RESULTS.',
  'V5',
  jsonb_build_object(
    'batch','9H_BATCH_1',
    'supported_count',4,
    'suggestive_count',4,
    'production_thresholds_authorized',false,
    'interaction_mining_authorized',false
  )
 )
)
insert into public.project_decisions(
 strategy_id,title,decision,rationale,evidence,affects_model_version,metadata_json
)
select pmpd.strategy_id,d.title,d.decision,d.rationale,d.evidence,d.affects_model_version,d.metadata_json
from pmpd cross join decisions d
where not exists (
 select 1 from public.project_decisions x
 where x.strategy_id=pmpd.strategy_id and x.title=d.title and x.status='active'
);

with pmpd as (
 select strategy_id from public.strategies where strategy_code='PMPD'
)
update public.project_state ps
set
 historical_dataset_status='PMPD_112_V1 / 2025 CERTIFIED; V5 9H OUTCOME DATASET V1 CERTIFIED; BATCH 1 COMPLETE',
 last_decision='9H Batch 1 complete: four replicated factor candidates supported; Batch 2 progression/retention/timing research active.',
 metadata_json=coalesce(ps.metadata_json,'{}'::jsonb) || jsonb_build_object(
   'v5_current_substep','9H-BATCH-2',
   'v5_9h_dataset_version','PMPD_V5_9H_RESEARCH_DATASET_V1',
   'v5_9h_dataset_run_fingerprint','5c085460e9d7a4367ca4bc40e5c71374e4634ecccd74de93ec26ba7c3f9e7fbb',
   'v5_9h_batch1_status','COMPLETE',
   'v5_9h_batch1_supported_count',4,
   'v5_9h_batch2_status','ACTIVE'
 ),
 updated_at=now()
from pmpd
where ps.strategy_id=pmpd.strategy_id;

commit;

with pmpd as (select strategy_id from public.strategies where strategy_code='PMPD')
select active_phase_code,active_phase_name,next_phase_code,next_phase_name,
       roadmap_version,historical_dataset_status,last_decision,
       metadata_json->>'v5_current_substep' as current_substep,
       metadata_json->>'v5_9h_batch1_status' as batch1_status,
       metadata_json->>'v5_9h_batch2_status' as batch2_status
from public.project_state ps join pmpd on pmpd.strategy_id=ps.strategy_id;
