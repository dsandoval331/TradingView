import json
from pathlib import Path
from unittest.mock import patch
import pytest
from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.control_plane_worker import run_one
from tr_platform.research import swing11_s2b as b

@pytest.mark.parametrize('authorized',[True,False])
def test_live_guard_before_any_input_access(tmp_path,authorized):
    snapshots=json.loads(Path('research_protocols/swing11/SWING11_S2B_FROZEN_AUTHORITY.json').read_text())
    job={'job_id':'synthetic-job','runner_job_id':'SW11-S2B','git_sha':'abc','parameters_json':{'mwe_uuid':b.MWE,'authorization_decision_id':b.AUTH,'scientific_outcomes_authorized':authorized,'input_registration_id':'synthetic-input','contract_snapshot':snapshots}}
    def fetch(config,table,filters):
        if table=='work_envelopes':return [{'status':'COMPLETE','metadata_json':{'state':'VERIFIED'}}]
        return [x for x in snapshots if filters['decision_id']=='eq.'+x['decision_id']]
    with patch.dict('os.environ',{'TR_RESEARCH_SHA':'abc'}),patch('cloud_compute.control_plane_worker.runner._git_sha',return_value='abc'),patch('cloud_compute.control_plane_worker.runner.WORK_ROOT',tmp_path),patch('cloud_compute.control_plane_worker.claim_job',return_value={'job':job,'attempt_id':'synthetic-attempt','attempt_no':1}),patch('cloud_compute.control_plane._fetch_rows',side_effect=fetch),patch('cloud_compute.control_plane_worker.materialize_job_inputs',return_value=[]) as materialize,patch('cloud_compute.control_plane_worker.runner.run_id',return_value=0),patch('cloud_compute.control_plane_worker._record_stream_logs'),patch('cloud_compute.control_plane_worker._persist_runner_artifacts',return_value=[{'artifact_id':'fixture','is_primary':True}]),patch('cloud_compute.control_plane_worker.update_job'),patch('cloud_compute.control_plane_worker.update_attempt'):
        code=run_one(ControlPlaneConfig('https://example.supabase.co','fixture'))
        if authorized:
            assert code==0;materialize.assert_called_once()
            context=json.loads((tmp_path/'job_inputs/swing10/execution_context.json').read_text())
            assert context['authorization_decision_id']==b.AUTH and context['scientific_outcomes_authorized']
            assert len(context['contract_snapshot'])==6
            assert materialize.call_args.kwargs['allowed_inputs'][0]['sha256']==b.p.SHA
        else:
            assert code!=0;materialize.assert_not_called()
