import json
import gzip
import hashlib
from pathlib import Path
from unittest.mock import patch
import pytest
from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.control_plane_worker import run_one
from tr_platform.research import swing11_s3p as p
from tests.test_swing11_s3p import frame

@pytest.mark.parametrize('authorized,changed,parent',[ (False,False,True),(True,False,True),(False,True,True),(False,False,False)])
def test_live_authority_guard_before_private_access(tmp_path,authorized,changed,parent):
 snapshots=json.loads(Path('research_protocols/swing11/SWING11_S3_FROZEN_AUTHORITY.json').read_text())
 job={'job_id':'synthetic-job','runner_job_id':'SW11-S3P','git_sha':'abc','parameters_json':{'mwe_uuid':p.MWE,'preflight_only':True,'scientific_outcomes_authorized':authorized,'input_registration_id':'synthetic-input','contract_snapshot':snapshots,'github_job_id':123}}
 def fetch(config,table,filters):
  if table=='work_envelopes':return [{'status':'COMPLETE' if parent else 'ACTIVE','metadata_json':{'state':'VERIFIED'}}]
  rows=[dict(x) for x in snapshots if filters['decision_id']=='eq.'+x['decision_id']]
  if changed:rows[0]['decision']='altered'
  return rows
 with patch.dict('os.environ',{'TR_RESEARCH_SHA':'abc'}),patch('cloud_compute.control_plane_worker.runner._git_sha',return_value='abc'),patch('cloud_compute.control_plane_worker.runner.WORK_ROOT',tmp_path),patch('cloud_compute.control_plane_worker.claim_job',return_value={'job':job,'attempt_id':'synthetic-attempt','attempt_no':1}),patch('cloud_compute.control_plane._fetch_rows',side_effect=fetch),patch('cloud_compute.control_plane_worker.materialize_job_inputs',return_value=[]) as mat,patch('cloud_compute.control_plane_worker.runner.run_id',return_value=0),patch('cloud_compute.control_plane_worker._record_stream_logs'),patch('cloud_compute.control_plane_worker._persist_runner_artifacts',return_value=[{'artifact_id':'fixture','is_primary':True}]),patch('cloud_compute.control_plane_worker.update_job'),patch('cloud_compute.control_plane_worker.update_attempt'):
  code=run_one(ControlPlaneConfig('https://example.supabase.co','fixture'))
  if authorized or changed or not parent:assert code!=0;mat.assert_not_called()
  else:
   assert code==0;mat.assert_called_once()
   ctx=json.loads((tmp_path/'job_inputs/swing10/execution_context.json').read_text())
   assert ctx['scientific_outcomes_authorized'] is False and ctx['preflight_only'] and ctx['github_job_id']==123
   assert mat.call_args.kwargs['allowed_inputs'][0]['sha256']==p.source.SHA

def context():
 return dict(mwe_uuid=p.MWE,preflight_only=True,scientific_outcomes_authorized=False,github_job_id=123,contract_snapshot=json.loads(Path('research_protocols/swing11/SWING11_S3_FROZEN_AUTHORITY.json').read_text()),materialized_inputs=[dict(input_id='synthetic-input',sha256=p.source.SHA,size_bytes=p.source.SIZE)],research_revision='1'*40,infrastructure_revision='2'*40,job_id='synthetic',attempt_id='synthetic',github_run_id=123)

def test_eight_artifact_schema_and_nonrecursive_manifest(tmp_path,monkeypatch):
 ctx=context();path=tmp_path/'job_inputs/swing10/execution_context.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(ctx));input=tmp_path/'job_inputs/swing11/development.csv';input.parent.mkdir(parents=True);input.write_bytes(b'SYNTHETIC_ONLY')
 monkeypatch.setenv('GITHUB_ACTIONS','true');monkeypatch.setattr(p.source,'verified_input',lambda blob:frame(100,60))
 result=p.run(tmp_path);assert len(result['output_paths'])==8
 manifest=json.loads((tmp_path/result['output_paths'][-1]).read_text());assert len(manifest['artifact_declarations'])==7 and not manifest['real_s3_outcomes_exposed']
 for rel,meta in result['output_artifact_metadata'].items():
  b=(tmp_path/rel).read_bytes();assert len(b)==meta['stored_size_bytes'] and hashlib.sha256(b).hexdigest()==meta['stored_sha256']
  if meta['storage_encoding']=='gzip':b=gzip.decompress(b)
  assert len(b)==meta['logical_size_bytes'] and hashlib.sha256(b).hexdigest()==meta['logical_sha256']
  if meta['logical_name'] in p.SCHEMAS:assert b.decode().splitlines()[0].split(',')==list(p.SCHEMAS[meta['logical_name']])

def test_run_rejects_real_execution_authority_without_reading_prices(tmp_path,monkeypatch):
 ctx=context();ctx['scientific_outcomes_authorized']=True;path=tmp_path/'job_inputs/swing10/execution_context.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(ctx));monkeypatch.setenv('GITHUB_ACTIONS','true')
 with pytest.raises(ValueError,match='outcome-blind'):p.run(tmp_path)
