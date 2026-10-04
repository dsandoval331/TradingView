"""Synthetic governed integration: never materialize a real validation input."""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from cloud_compute import research_revision_adapter as a
from cloud_compute.certify_dispatch_contracts import selected_tests
from tr_platform.research import swing10_s2_b5_validation as v
from tr_platform.research import swing10_s2_b5_validation_contract as c
from test_swing10_s2_b5_validation import panel

def test_adapter_whitelist_and_exact_bundle(tmp_path):
    copied=[]
    def materialize(repo,sha,path,destination):
        copied.append((sha,path));destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text('x')
    def execute(argv,**kwargs):
        Path(argv[-1]).write_text(json.dumps({'status':'PASS','artifact':'x'}))
        assert 'swing10_s2_b5_validation' in argv[2]
        return SimpleNamespace(returncode=0,stderr='')
    with patch.object(a,'materialize_module',materialize),patch.object(a.subprocess,'run',execute):
        assert a._run_b5_validation_bundle(tmp_path,'f'*40,tmp_path/'bundle',tmp_path)['status']=='PASS'
    assert len(copied)==5 and all(sha=='f'*40 for sha,_ in copied)
    assert a.GOVERNED_RESEARCH_TARGETS['SW10-S2-B5'].execution_mode=='swing10_b5_validation_bundle'

def test_dispatch_certification_only_registered_b5_suite():
    tests=selected_tests('SW10-S2-B5')
    assert 'tests/test_swing10_s2_b5_validation.py' in tests
    assert 'tests/test_swing10_s2_b5_integration.py' in tests

def test_materialized_context_required_before_any_panel_read(tmp_path,monkeypatch):
    folder=tmp_path/'job_inputs/swing10';folder.mkdir(parents=True)
    (folder/'execution_context.json').write_text(json.dumps({'materialized_inputs':[]}))
    monkeypatch.setattr(v,'verify_input',lambda path:pytest.fail('must fail before data access'))
    with pytest.raises(ValueError,match='certified parent'):v.run(tmp_path)

def test_exact_seven_outputs_manifest_registration_identities_synthetic_only(tmp_path,monkeypatch):
    folder=tmp_path/'job_inputs/swing10';folder.mkdir(parents=True)
    context={'job_id':'synthetic','attempt_id':'fixture','materialized_inputs':[{'input_id':'input','sha256':c.INPUT_SHA,'size_bytes':c.INPUT_BYTES}],
             'parent_input_id':c.INPUT_ID,'input_registration_id':'input','research_revision':'f'*40,'infrastructure_revision':'e'*40}
    (folder/'execution_context.json').write_text(json.dumps(context))
    monkeypatch.setattr(v,'verify_input',lambda path:panel(83))
    result=v.run(tmp_path)
    assert len(result['output_paths'])==7 and len(result['output_artifact_ids'])==7
    manifest=json.loads((tmp_path/result['output_paths'][-1]).read_text())
    assert len(manifest['artifacts'])==6 and manifest['market']['primary_estimand']=='gamma'
    assert len(manifest['case_specific_block_definitions'])==36
    assert manifest['multiple_testing']['family_tests']==9
    assert manifest['manifest_identity']['integrity'].startswith('external')
    assert manifest['protected_data_access'] is False
    assert sum(r['limited_temporal_capacity'] for r in manifest['registry'])==2
    import hashlib
    for row in manifest['artifacts']:
        path=tmp_path/result['output_paths'][c.FILES.index(row['name'])]
        assert row['size_bytes']==path.stat().st_size and row['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()

def test_latest_attempt_storage_readback_routing():
    text=Path('cloud_compute/b2_readback_if_applicable.py').read_text()
    assert "elif jobs[0]['runner_job_id'] == 'SW10-S2-B5':" in text
    assert 'swing10_s2_b5_validation_contract import FILES' in text
