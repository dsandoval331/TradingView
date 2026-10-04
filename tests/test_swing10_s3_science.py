import copy
import csv
import json
from pathlib import Path
import pytest
from tr_platform.research import swing10_s3_science as science
from tr_platform.research import swing10_s3_engine as engine
from tr_platform.research import swing10_s3_preparation as prep
from cloud_compute import s3_activation_gate as gate

def valid_context():
    return dict(mwe_uuid=science.MWE,protocol_decision_id=science.DECISION,scientific_outcomes_authorized=True,operational_activation_verified=True,github_run_id='synthetic-regression-run',input_registration_id='exact-input',materialized_inputs=[dict(input_id='exact-input',sha256=prep.DEVELOPMENT_SHA,size_bytes=prep.DEVELOPMENT_BYTES,object_path=prep.OBJECT)])

@pytest.mark.parametrize('change',[{'mwe_uuid':'S3P'},{'scientific_outcomes_authorized':False},{'operational_activation_verified':False},{'protocol_decision_id':'different'},{'github_run_id':None},{'materialized_inputs':[]},{'materialized_inputs':[dict(input_id='B5',sha256=prep.CONSUMED_B5_SHA,size_bytes=792664,object_path='B5')]}])
def test_authority_fail_closed_before_data(monkeypatch,change):
    monkeypatch.setenv('GITHUB_ACTIONS','true');context=valid_context();context.update(change)
    with pytest.raises(ValueError):science.admit_context(context)

def test_no_local_real_science(monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS',raising=False)
    with pytest.raises(ValueError,match='governed GitHub'):science.admit_context(valid_context())

def test_exact_admission(monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS','true');assert science.admit_context(valid_context())['input_id']=='exact-input'

def fixture_cohorts():
    out={}
    for i in range(16):
        out[f'{i:03}']={}
        for side in prep.SIDES:
            out[f'{i:03}'][side]={}
            for j in range(8):
                bars=[]
                for k in range(10):
                    c=100+(k+1)*(.08+i*.005+j*.001)*(1 if side=='LONG_LOW' else -1)
                    bars.append(dict(open=100.,high=max(100,c)+.05,low=min(100,c)-.05,close=c,volume=100.,date=f'FIXTURE_SESSION_{i}_{k}'))
                out[f'{i:03}'][side][f'FIXTURE_S{j}']={'prior':[dict(open=100.,high=100.5,low=99.5,close=100.,volume=100.)]*5,'bars':bars}
    return out

def test_streamed_full_frozen_science_matches_certified_engine(tmp_path):
    contract=json.loads(Path('research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.proposed.json').read_text());cohorts=fixture_cohorts()
    original=engine.build_synthetic_tables(cohorts,contract);sink=science.PathSink(tmp_path/'paths.csv',contract['artifact_schemas']['s3_event_paths.csv'])
    streamed=engine.calculate_frozen_tables(cohorts,contract,path_sink=sink);sink.close()
    assert sink.count==len(original['s3_event_paths.csv'])
    rows=list(csv.DictReader((tmp_path/'paths.csv').open()))
    assert len(rows)==36*16*8*10 and list(rows[0])==contract['artifact_schemas']['s3_event_paths.csv']
    for name in contract['artifact_schemas']:
        if name!='s3_event_paths.csv':assert streamed[name]==original[name]
    assert sum(r['selected_for_canonical_review'] for r in streamed['s3_candidate_summary.csv'])<=2

def test_stream_schema_fails_closed(tmp_path):
    sink=science.PathSink(tmp_path/'paths.csv',['symbol','date'])
    with pytest.raises(ValueError,match='schema drift'):sink.append({'symbol':'FIXTURE'})
    sink.close()

def test_runtime_no_context_never_reads_source(tmp_path,monkeypatch):
    context=tmp_path/'job_inputs/swing10/execution_context.json';context.parent.mkdir(parents=True);context.write_text(json.dumps(valid_context()))
    monkeypatch.delenv('GITHUB_ACTIONS',raising=False)
    with pytest.raises(ValueError,match='governed GitHub'):science.run(tmp_path)
    assert not (tmp_path/'research_outputs').exists()

def test_no_activation_no_private_source(monkeypatch):
    calls=[]
    monkeypatch.setattr(gate,'_fetch_rows',lambda *a:calls.append(a))
    with pytest.raises(RuntimeError,match='envelope'):gate.verify_activation(None,{'mwe_uuid':'S3P'})
    assert calls==[]

@pytest.mark.parametrize('failure',['mwe','decision','job','attempt','missing_artifact','missing_readback','hash','rows','evidence'])
def test_activation_fail_closed(monkeypatch,failure):
    frozen=json.loads(Path('research_protocols/swing10/SW10_S3_CANDIDATE_PROTOCOL_V1.persisted.json').read_text());schemas=frozen['metadata_json']['frozen_contract']['artifact_schemas']
    evidence=dict(job_id='cert-job',attempt_id='cert-attempt',research_sha='exact-sha')
    params=dict(mwe_uuid=gate.MWE,protocol_decision_id=gate.DECISION,scientific_outcomes_authorized=True,parent_input_id='131b6bd5-65d1-4dc7-a856-3300f73babcb',operational_activation_evidence=evidence)
    records={'work_envelopes':[dict(status='ACTIVE',frozen_contract_json={'scientific_execution_authorized':True},metadata_json={'operational_activation_verified':True,'operational_activation_evidence':copy.deepcopy(evidence)})],'project_decisions':[copy.deepcopy(frozen)],'research_jobs':[dict(runner_job_id='SW10-S3-ARTIFACT-CERT',status='succeeded',git_sha='exact-sha')],'research_job_attempts':[dict(status='succeeded',attempt_id='cert-attempt',git_sha='exact-sha')],'research_job_artifacts':[dict(artifact_id=n,size_bytes=1,sha256='digest',metadata_json={'logical_name':n,'rows':3138120,'logical_size_bytes':100000000}) for n in schemas],'research_artifact_readbacks':[dict(artifact_id=n,size_bytes=1,sha256='digest',verified_sha256=True,source_git_sha='exact-sha',metadata_json={'source_attempt_id':'cert-attempt'}) for n in schemas]}
    if failure=='mwe':records['work_envelopes'][0]['status']='COMPLETE'
    elif failure=='decision':records['project_decisions'][0]['metadata_json']['status']='DRAFT'
    elif failure=='job':records['research_jobs'][0]['git_sha']='wrong'
    elif failure=='attempt':records['research_job_attempts'][0]['status']='failed'
    elif failure=='missing_artifact':records['research_job_artifacts'].pop()
    elif failure=='missing_readback':records['research_artifact_readbacks'].pop()
    elif failure=='hash':records['research_artifact_readbacks'][0]['sha256']='wrong'
    elif failure=='evidence':records['work_envelopes'][0]['metadata_json']['operational_activation_evidence']['attempt_id']='wrong'
    else:
        for a in records['research_job_artifacts']:a['metadata_json']['rows']=1
    monkeypatch.setattr(gate,'_fetch_rows',lambda config,table,query:records[table])
    with pytest.raises(RuntimeError):gate.verify_activation(None,params)
