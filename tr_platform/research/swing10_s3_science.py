"""Exact frozen S3 development science; separately authorized governed envelope only."""
import csv
import hashlib
import json
import os
from pathlib import Path
import uuid
from cloud_compute.streaming_artifacts import package
from tr_platform.research import swing10_s3_preparation as prep
from tr_platform.research.swing10_s3_preflight import validate_freeze,decode_verified,PROPOSAL_SHA
from tr_platform.research.swing10_s3_engine import calculate_frozen_tables

MWE='3ac865ff-4f78-4f2c-807d-e579604ea39f'
DECISION='21091322-b757-42e5-9918-dba46b2e1252'

class PathSink:
    def __init__(self,path,columns):
        self.columns=columns;self.count=0;self.stream=Path(path).open('w',newline='',encoding='utf-8')
        self.writer=csv.DictWriter(self.stream,fieldnames=columns,lineterminator='\n');self.writer.writeheader()
    def append(self,row):
        if set(row)!=set(self.columns):raise ValueError('frozen path schema drift')
        self.writer.writerow(row);self.count+=1
    def close(self):self.stream.close()

def admit_context(context):
    if os.environ.get('GITHUB_ACTIONS')!='true' or not context.get('github_run_id'):
        raise ValueError('real science restricted to governed GitHub Actions')
    if context.get('mwe_uuid')!=MWE or context.get('protocol_decision_id')!=DECISION or context.get('scientific_outcomes_authorized') is not True or context.get('operational_activation_verified') is not True:
        raise ValueError('exact separately authorized envelope plus verified activation required')
    items=context.get('materialized_inputs',[])
    if len(items)!=1 or items[0]['input_id']!=context.get('input_registration_id') or items[0]['sha256']!=prep.DEVELOPMENT_SHA or items[0]['size_bytes']!=prep.DEVELOPMENT_BYTES or items[0]['object_path']!=prep.OBJECT:
        raise ValueError('only exact immutable development object; B5/S5 denied')
    return items[0]

def make_cohorts(panel,dates,symbols):
    # Eligibility and four-block dates fixed before passing bars to engine.
    result={}
    for index,date in enumerate(dates):
        if not prep.common_date_eligibility(dates,date):continue
        low,high=prep.tail_membership([(s,panel[date][s]['close']) for s in symbols])
        sides={}
        for side,selected in [('LONG_LOW',low),('SHORT_HIGH',high)]:
            sides[side]={s:{'prior':[dict(panel[d][s],date=d) for d in dates[index-4:index+1]],'bars':[dict(panel[d][s],date=d) for d in dates[index+1:index+11]]} for s in sorted(selected)}
        result[date]=sides
    if len(result)!=379 or any(len(rows)!=23 for sides in result.values() for rows in sides.values()):raise ValueError('certified outcome-blind common eligibility drift')
    return result

def run(work_root):
    work_root=Path(work_root);root=Path(__file__).resolve().parents[2]
    context=json.loads((work_root/'job_inputs/swing10/execution_context.json').read_text());item=admit_context(context)
    proposal=root/'research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.proposed.json';frozen=root/'research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.persisted.json'
    if hashlib.sha256(proposal.read_bytes()).hexdigest()!=PROPOSAL_SHA:raise ValueError('unchanged prospective contract byte hash required')
    contract=json.loads(proposal.read_text());snapshot=json.loads(frozen.read_text());validate_freeze(snapshot,contract)
    blob=(work_root/'job_inputs/swing10/s3_development_daily_history.csv').read_bytes();panel,dates,symbols=decode_verified(blob)
    cohorts=make_cohorts(panel,dates,symbols);out=work_root/'research_outputs/swing10/s3';out.mkdir(parents=True,exist_ok=True)
    sink=PathSink(out/'s3_event_paths.csv',contract['artifact_schemas']['s3_event_paths.csv'])
    try:tables=calculate_frozen_tables(cohorts,contract,path_sink=sink)
    finally:sink.close()
    if sink.count!=3138120 or len(tables['s3_event_exits.csv'])!=313812 or len(tables['s3_candidate_registry.csv'])!=36 or len(tables['s3_candidate_summary.csv'])!=12:raise ValueError('complete frozen cell/family/path accounting required')
    tables['s3_semantic_integrity.csv']=[{'check_id':check,'pass':True,'reason':reason,'input_uuid':item['input_id'],'input_sha256':item['sha256'],'input_bytes':item['size_bytes'],'B5_read':False,'S5_read':False,'future_information':False,'unavailable_cells':0} for check,reason in [('FROZEN_PROTOCOL','prospective unchanged contract independently verified'),('IMMUTABLE_INPUT','fresh SHA/size/structure checked before outcomes'),('OPERATIONAL_ACTIVATION','full-scale synthetic private/SQL-byte certification passed before source access'),('CAUSAL_ENTRY','same-date inclusive 20/80; next-open; complete prior5/full10 common calendar'),('PROTECTED_DENIAL','consumed B5 and all post2026-08-27 sources denied'),('COMPLETE_REGISTRY','36cells;12families;fixed costs and equal-weight all3caps; no outcome exclusions')]]
    paths=[];ids={};metadata={};declarations=[];primary=None
    for name,columns in contract['artifact_schemas'].items():
        if not name.endswith('.csv'):continue
        path=out/name
        if name!='s3_event_paths.csv':
            with path.open('w',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=columns,lineterminator='\n');writer.writeheader();writer.writerows(tables[name])
        stored,meta=package(path);rel=str(stored.relative_to(work_root));identity=str(uuid.uuid4());paths.append(rel);ids[rel]=identity;metadata[rel]=meta
        if name=='s3_candidate_summary.csv':primary=rel
        declarations.append({'name':name,'artifact_id':identity,'object_path':f"artifacts/{context['job_id']}/{context['attempt_id']}/{stored.name}",**meta})
    manifest=tables['sw10_s3_manifest.json'];manifest.update(protocol_snapshot_sha256=hashlib.sha256(frozen.read_bytes()).hexdigest(),execution_ids=context,research_sha=context['research_revision'],infra_sha=context['infrastructure_revision'],input_identities=[item],artifact_identities_hashes_bytes=declarations,synthetic_only=False,scientific_execution_authorized=True,protected_flags={'B5_read':False,'S5_read':False,'post_development_read':False,'S6_locked':True},billing_evidence={'executor':'existing governed GitHub Actions','paid_fallback':False,'billing_evidence_available':False},input_structure={'rows':44128,'symbols':112,'sessions':394,'first':'2025-02-03','last':'2026-08-27'},path_rows=sink.count,event_exit_rows=len(tables['s3_event_exits.csv']),operational_activation=context['operational_activation_evidence'],selection_authority='mechanical maximum one per side only; no S4 transition',limitations=['previously used S2 development, not independent validation','daily adjusted OHLC sequence ambiguity stop-first; no intraday precision','cohort index is not a self-financing portfolio; short borrow and execution stress deferred to S4'])
    path=out/'sw10_s3_manifest.json';path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');stored,meta=package(path);rel=str(stored.relative_to(work_root));paths.append(rel);ids[rel]=str(uuid.uuid4());metadata[rel]=meta
    return {'status':'PASS','artifact':primary,'output_paths':paths,'output_artifact_ids':ids,'output_artifact_metadata':metadata}
