from pathlib import Path
import json
import pytest
from cloud_compute import research_revision_adapter as adapter
from cloud_compute.certify_dispatch_contracts import selected_tests
from research_runner import runner
from tr_platform.research import swing10_s3_preflight as audit


def test_explicit_preflight_registry_only():
    ids={r['id'] for r in runner.JOBS}
    assert 'SW10-S3-PREFLIGHT' in ids
    assert 'SW10-S3' in ids
    assert adapter.GOVERNED_RESEARCH_TARGETS['SW10-S3'].execution_mode=='swing10_s3_scientific_bundle'
    assert adapter.GOVERNED_RESEARCH_TARGETS['SW10-S3-PREFLIGHT'].execution_mode=='swing10_s3_preflight_bundle'


def test_preflight_bundle_exact_snapshot_and_no_science(monkeypatch,tmp_path):
    paths=[]
    def materialize(repo,sha,path,dest):
        paths.append((sha,path));dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text('# synthetic fixture');return dest
    monkeypatch.setattr(adapter,'materialize_module',materialize)
    class Result:
        returncode=0
        stderr=''
    def process(args,**kwargs):
        assert 'swing10_s3_preflight import run' in args[2]
        assert 'engine' not in args[2]
        Path(args[-1]).write_text(json.dumps({'status':'PASS'}))
        return Result()
    monkeypatch.setattr(adapter.subprocess,'run',process)
    assert adapter._run_s3_preflight_bundle(tmp_path,'1'*40,tmp_path/'bundle',tmp_path)['status']=='PASS'
    assert len(paths)==4 and all(sha=='1'*40 for sha,p in paths)
    assert not any('engine' in p for _,p in paths)
    assert sum(p.endswith('.persisted.json') for _,p in paths)==1


def test_bundle_failure_preserved(monkeypatch,tmp_path):
    def materialize(repo,sha,path,dest):
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text('fixture');return dest
    monkeypatch.setattr(adapter,'materialize_module',materialize)
    class Result:
        returncode=1
        stderr='immutable byte identity mismatch'
    monkeypatch.setattr(adapter.subprocess,'run',lambda *a,**k:Result())
    with pytest.raises(RuntimeError,match='immutable byte identity'):
        adapter._run_s3_preflight_bundle(tmp_path,'1'*40,tmp_path/'bundle',tmp_path)


def test_dispatch_certifies_all_frozen_regressions():
    files=selected_tests('SW10-S3-PREFLIGHT')
    assert 'tests/test_swing10_s3_preparation.py' in files
    assert 'tests/test_swing10_s3_frozen.py' in files
    assert 'tests/test_swing10_s3_integration.py' in files


def test_runtime_denies_missing_exact_preflight_context(tmp_path):
    context=tmp_path/'job_inputs/swing10/execution_context.json';context.parent.mkdir(parents=True)
    context.write_text(json.dumps({'mwe_uuid':'another-mwe','scientific_outcomes_authorized':True}))
    with pytest.raises(ValueError,match='outcome-blind envelope'):
        audit.run(tmp_path)


def test_runtime_denies_b5_materialization(tmp_path):
    context=tmp_path/'job_inputs/swing10/execution_context.json';context.parent.mkdir(parents=True)
    context.write_text(json.dumps({'mwe_uuid':audit.MWE,'protocol_decision_id':audit.DECISION,'scientific_outcomes_authorized':False,'preflight_only':True,'materialized_inputs':[{'input_id':'86045cd0-8e49-4261-aed9-3f24bfb5ff07','sha256':'b905affcb0843a4d313557fc59fc543a46413258f2c49a68f1eb87d338e55915','size_bytes':792664,'object_path':'B5-prohibited'}]}))
    with pytest.raises(ValueError,match='B5/S5 denied'):
        audit.run(tmp_path)


def test_future_values_never_affect_signal_cohort():
    dates=[f'2025-02-{i:02}' for i in range(3,28)]
    symbols=[f'S{i:03}' for i in range(112)]
    panel={d:{s:dict(open=100.,high=101.,low=99.,close=float(i+1),volume=100.) for i,s in enumerate(symbols)} for d in dates}
    a=audit.coverage(panel,dates,symbols)
    for s in symbols:panel[dates[10]][s]['close']=10000.
    b=audit.coverage(panel,dates,symbols)
    assert [r for r in a[1] if r['signal_date']==dates[5]]==[r for r in b[1] if r['signal_date']==dates[5]]
    assert a[0]==b[0]


def test_protected_admission_before_any_download(monkeypatch,tmp_path):
    from cloud_compute import input_materializer as materializer
    from cloud_compute.control_plane import ControlPlaneConfig
    calls=[]
    allowed={"input_id":"approved", "object_path":"approved.csv", "object_size_bytes":1, "sha256":"abc", "metadata_json":{"bucket_name":"private", "local_relative_path":"approved.csv"}}
    prohibited={**allowed,"input_id":"consumed-B5", "object_path":"B5.csv"}
    monkeypatch.setattr(materializer,'fetch_job_inputs',lambda *a:[allowed,prohibited])
    monkeypatch.setattr(materializer,'_download_object',lambda *a:calls.append(a))
    with pytest.raises(RuntimeError,match='before any private download'):
        materializer.materialize_job_inputs(ControlPlaneConfig('https://fixture.invalid','fixture'),job_id='fixture',work_root=tmp_path,allowed_inputs=[allowed])
    assert calls==[]


def test_protected_admission_rejects_object_bucket_or_path_drift(monkeypatch,tmp_path):
    from cloud_compute import input_materializer as materializer
    from cloud_compute.control_plane import ControlPlaneConfig
    allowed={"input_id":"approved", "object_path":"approved.csv", "object_size_bytes":1, "sha256":"abc", "metadata_json":{"bucket_name":"private", "local_relative_path":"approved.csv"}}
    calls=[];monkeypatch.setattr(materializer,'_download_object',lambda *a:calls.append(a))
    variants=[{**allowed,'sha256':'B5SHA'},{**allowed,'object_path':'S5.csv'},{**allowed,'metadata_json':{'bucket_name':'other','local_relative_path':'approved.csv'}}]
    for row in variants:
        monkeypatch.setattr(materializer,'fetch_job_inputs',lambda *a:[row])
        with pytest.raises(RuntimeError,match='before any private download'):
            materializer.materialize_job_inputs(ControlPlaneConfig('https://fixture.invalid','fixture'),job_id='fixture',work_root=tmp_path,allowed_inputs=[allowed])
    assert calls==[]
