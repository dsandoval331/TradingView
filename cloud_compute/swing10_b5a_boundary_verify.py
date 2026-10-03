"""Read-only provider availability verification for the preserved B5A acquisition."""
from __future__ import annotations
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import pandas as pd
from cloud_compute.control_plane import ControlPlaneConfig, _fetch_rows, create_artifact
from cloud_compute.storage_poc import DEFAULT_BUCKET, _upload_object
from cloud_compute.artifact_readback import run as readback
from cloud_compute.research_revision_adapter import materialize_module

JOB_ID='2cc99ebc-66f6-4bf5-a4d7-b6fc46cdb6a4'
ATTEMPT_ID='0d44dde0-82c2-40b4-b0db-64881361e603'
RESEARCH_SHA='6449de82add1c1016185116e650663c3204e9661'
FLOOR='2003-09-10'
CUTOFF=pd.Timestamp('2025-02-03')
FORBIDDEN={'forward_return','forward_returns','effect_size','p_value','mfe','mae','win_rate','profitability'}


def guard_source(source):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Subscript) and isinstance(node.slice,ast.Constant) and node.slice.value in {'c','o','h','l','v'}|FORBIDDEN:
            raise ValueError('outcome/price evaluation prohibited')
        if isinstance(node,ast.Call):
            name=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
            if name in {'shift','pct_change','diff','hac_mean','bh_adjust','read_csv','read_parquet','read_sql'}:
                raise ValueError('scientific/outcome primitive prohibited')


def observed_dates(payload):
    rows=payload.get('results') or []
    if any(FORBIDDEN.intersection(row) for row in rows):raise ValueError('outcome-bearing fields prohibited')
    dates=[pd.Timestamp(row['t'],unit='ms',tz='UTC').tz_convert('America/New_York').normalize().tz_localize(None) for row in rows]
    if any(d>=CUTOFF for d in dates):raise ValueError('discovery/protected date prohibited')
    return dates


def classify(earliest, probes):
    start=pd.Timestamp(earliest)
    records={label:(payload,record) for label,payload,record,raw in probes}
    payload,record=records['earliest_available_day']
    verified_current=record.get('http_status')==200 and payload.get('adjusted') is True and observed_dates(payload)==[start]
    earlier_unavailable=True
    for label in ('earlier_aapl_history','earlier_spy_history'):
        payload,record=records[label]
        earlier_unavailable &= record.get('http_status')==403 or (record.get('http_status')==200 and not observed_dates(payload))
    return 'MAXIMUM_PROVIDER_EXPOSED_PRE_DISCOVERY_COVERAGE_VERIFIED' if verified_current and earlier_unavailable else 'PRE_DISCOVERY_COVERAGE_REQUIRES_RECOVERY'


def main():
    guard_source(Path(__file__).read_text())
    config=ControlPlaneConfig(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SECRET_KEY'])
    jobs=_fetch_rows(config,'research_jobs',{'job_id':f'eq.{JOB_ID}','limit':'2'})
    attempts=_fetch_rows(config,'research_job_attempts',{'job_id':f'eq.{JOB_ID}','attempt_id':f'eq.{ATTEMPT_ID}','limit':'2'})
    if len(jobs)!=1 or jobs[0]['status']!='succeeded' or jobs[0]['git_sha']!=RESEARCH_SHA or len(attempts)!=1 or attempts[0]['status']!='succeeded' or attempts[0]['git_sha']!=RESEARCH_SHA:
        raise RuntimeError('exact succeeded B5A job/attempt required')
    registry=_fetch_rows(config,'research_artifact_readbacks',{'job_id':f'eq.{JOB_ID}','object_path':f'eq.artifacts/{JOB_ID}/{ATTEMPT_ID}/daily_acquisition_source_registry.json','limit':'2'})
    if len(registry)!=1 or not registry[0]['verified_sha256']:raise RuntimeError('verified exact source registry required')
    sources=json.loads(registry[0]['content_text'])['sources']
    if len(sources)!=112 or 'SPY' not in {s['symbol'] for s in sources}:raise RuntimeError('all112/SPY source identities required')
    starts=[pd.Timestamp(s['source_record']['timestamp_min'],unit='ms',tz='UTC').tz_convert('America/New_York').normalize().tz_localize(None) for s in sources]
    if len(set(starts))!=1:raise RuntimeError('nonuniform starts require explicit availability audit')
    earliest=starts[0]; prior=earliest-pd.Timedelta(days=1)
    key=os.environ.get('MASSIVE_API_KEY') or os.environ.get('TR_MASSIVE_API_KEY')
    if not key:raise RuntimeError('existing credential absent; value not requested')
    with tempfile.TemporaryDirectory(prefix='b5a-boundary-verify-') as td:
        root=Path(td); module=root/'acquisition.py'
        materialize_module(Path.cwd(),RESEARCH_SHA,'tr_platform/research/swing10_s2_b5_acquisition.py',module)
        spec=importlib.util.spec_from_file_location('exact_b5a_provider',module); provider_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(provider_module);provider_module.guard_source(module.read_text());provider=provider_module.Provider(key)
        probes=[]
        for label,symbol,start,end in [('earliest_available_day','AAPL',earliest,earliest),('earlier_aapl_history','AAPL',FLOOR,prior),('earlier_spy_history','SPY',FLOOR,prior)]:
            payload,record,raw=provider.request(symbol,start,end)
            if payload is None or raw is None:raise RuntimeError('provider verification transport unavailable')
            observed_dates(payload);probes.append((label,payload,record,raw))
        classification=classify(earliest,probes)
        report={'classification':classification,'job_id':JOB_ID,'source_attempt_id':ATTEMPT_ID,'source_research_sha':RESEARCH_SHA,'source_infrastructure_sha':attempts[0]['metadata_json']['infrastructure_sha'],'verification_infrastructure_sha':os.environ['GITHUB_SHA'],'verification_run_id':os.environ['GITHUB_RUN_ID'],'verification_job_name':os.environ.get('GITHUB_JOB'),'credential_available':True,'request_start_is_not_returned_coverage_start':True,'source_requested_start':FLOOR,'source_returned_start':str(earliest.date()),'source_returned_end':'2025-01-31','all112_uniform_start_verified':True,'provider_request_count':3,'probe_records':[{'label':label,**record} for label,payload,record,raw in probes],'validation_outcomes_read':False,'validation_outcomes_computed':False,'protected_data_access':False,'paid_upgrade_selected':False,'literal_zero_billing_verified':False,'scientific_interval_selected':False}
        paths=[]
        for label,payload,record,raw in probes:
            p=root/f'raw_entitlement_probe_{label}_{hashlib.sha256(raw).hexdigest()}.json';p.write_bytes(raw);paths.append(p)
        blob=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode();p=root/f'entitlement_boundary_verification_{hashlib.sha256(blob).hexdigest()}.json';p.write_bytes(blob);paths.append(p)
        for p in paths:
            blob=p.read_bytes();object_path=f'artifacts/{JOB_ID}/{ATTEMPT_ID}/{p.name}'
            _upload_object(config.supabase_url,config.secret_key,DEFAULT_BUCKET,object_path,p,allow_existing=True)
            existing=_fetch_rows(config,'research_job_artifacts',{'job_id':f'eq.{JOB_ID}','attempt_id':f'eq.{ATTEMPT_ID}','object_path':f'eq.{object_path}','limit':'2'})
            if existing:
                if len(existing)!=1 or existing[0]['sha256']!=hashlib.sha256(blob).hexdigest() or existing[0]['size_bytes']!=len(blob):raise RuntimeError('immutable verification object parity failure')
            else:
                create_artifact(config,{'job_id':JOB_ID,'attempt_id':ATTEMPT_ID,'artifact_type':'research_output','storage_backend':'supabase_storage','bucket_name':DEFAULT_BUCKET,'object_path':object_path,'media_type':'application/json','size_bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'is_primary':False,'metadata_json':{'role':'OUTCOME_BLIND_ENTITLEMENT_BOUNDARY_VERIFICATION','verification_run_id':os.environ['GITHUB_RUN_ID'],'verification_infrastructure_sha':os.environ['GITHUB_SHA'],'source_registry_artifact_id':registry[0]['artifact_id']}})
        os.environ['TR_GIT_SHA']=os.environ['GITHUB_SHA'];rb=readback(JOB_ID,[p.name for p in paths],attempt_id=ATTEMPT_ID)
        if rb['count']!=4:raise RuntimeError('all four operational verification artifacts required')
        print(json.dumps({'classification':classification,'artifact_readbacks':rb['count'],'provider_requests':3,'source_returned_start':str(earliest.date()),'credential_value_exposed':False}))
        if classification!='MAXIMUM_PROVIDER_EXPOSED_PRE_DISCOVERY_COVERAGE_VERIFIED':raise RuntimeError('additional acquisition recovery required; outcomes remain uncomputed')


if __name__=='__main__':main()
