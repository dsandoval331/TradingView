"""Select governed contract checks without running outcome tests in preflight."""
import argparse
import os
import subprocess
import sys
from cloud_compute.control_plane import ControlPlaneConfig, _fetch_rows

BASE = ['tests/test_ccp5_control_plane.py','tests/test_ccp5_control_plane_worker.py',
        'tests/test_ccp8_autonomous_loop.py','tests/test_ccp9_exact_claim.py',
        'tests/test_ccp10_input_materializer.py','tests/test_ccp11_artifact_contract.py',
        'tests/test_research_revision_adapter.py','tests/test_swing10_input_prepare.py']


def selected_tests(runner_id):
    if runner_id == "SW10-S3":
        return BASE + ["tests/test_swing10_s3_preparation.py", "tests/test_swing10_s3_frozen.py", "tests/test_swing10_s3_integration.py", "tests/test_swing10_s3_streaming.py", "tests/test_swing10_s3_chunks.py", "tests/test_swing10_s3_science.py"]
    if runner_id == "SW10-S3-ARTIFACT-CERT":
        return BASE + ["tests/test_swing10_s3_preparation.py", "tests/test_swing10_s3_frozen.py", "tests/test_swing10_s3_integration.py", "tests/test_swing10_s3_streaming.py", "tests/test_swing10_s3_chunks.py"]
    if runner_id == "SW10-S3-PREFLIGHT":
        return BASE + ["tests/test_swing10_s3_preparation.py", "tests/test_swing10_s3_frozen.py", "tests/test_swing10_s3_integration.py"]
    if runner_id == 'SW10-S2-B5':
        return BASE + ['tests/test_swing10_s2_b5_preparation.py','tests/test_swing10_s2_b5_validation.py','tests/test_swing10_s2_b5_integration.py']
    if runner_id == 'SW10-S2-B5-ACQUISITION':
        return BASE + ['tests/test_swing10_s2_b5_acquisition.py']
    if runner_id == 'SW10-S2-B5-PREFLIGHT':
        return BASE + ['tests/test_swing10_s2_b5_preflight.py']
    if runner_id == 'SW10-S2-B4':
        return BASE + ['tests/test_swing10_s2_b4_contract.py','tests/test_swing10_s2_b4_preflight.py','tests/test_swing10_s2_b4.py']
    if runner_id == 'SW10-S2-B4-PREFLIGHT':
        return BASE + ['tests/test_swing10_s2_b4_preflight.py']
    if runner_id == 'SW10-S2-B3':
        return BASE + ['tests/test_swing10_s2_b3_preflight.py','tests/test_swing10_s2_b3_continuous_preflight.py','tests/test_swing10_s2_b3.py']
    if runner_id == 'SW10-S2-B3-CONTINUOUS-PREFLIGHT':
        return BASE + ['tests/test_swing10_s2_b3_preflight.py','tests/test_swing10_s2_b3_continuous_preflight.py']
    return BASE + (['tests/test_swing10_s2_b3_preflight.py'] if runner_id == 'SW10-S2-B3-PREFLIGHT'
                   else ['tests/test_swing10_s2_b2_core.py','tests/test_swing10_s2_b2.py'])


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--job-id',required=True)
    a=p.parse_args()
    config=ControlPlaneConfig(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SECRET_KEY'])
    jobs=_fetch_rows(config,'research_jobs',{'job_id':f'eq.{a.job_id}','limit':'2'})
    if len(jobs)!=1:
        raise RuntimeError('exact job not found for certification')
    raise SystemExit(subprocess.call([sys.executable,'-m','pytest','-q',*selected_tests(jobs[0]['runner_job_id'])]))


if __name__=='__main__':main()

