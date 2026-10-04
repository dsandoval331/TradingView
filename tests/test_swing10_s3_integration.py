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
    assert 'SW10-S3' not in ids
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
