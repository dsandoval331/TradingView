"""Read back all seven B2 artifacts; harmless no-op for other runners."""
import argparse
import json
import os
from cloud_compute.control_plane import ControlPlaneConfig, _fetch_rows
from cloud_compute.artifact_readback import run


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--job-id', required=True)
    a = p.parse_args()
    config = ControlPlaneConfig(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SECRET_KEY'])
    jobs = _fetch_rows(config, 'research_jobs', {'job_id': f'eq.{a.job_id}', 'limit': '2'})
    if len(jobs) != 1:
        raise RuntimeError('exact job not found')
    if jobs[0]['runner_job_id'] not in {'SW10-S2-B2', 'SW10-S2-B3-PREFLIGHT', 'SW10-S2-B3-CONTINUOUS-PREFLIGHT', 'SW10-S2-B3', 'SW10-S2-B4-PREFLIGHT'}:
        print('B2_READBACK_NOT_APPLICABLE')
        return
    if jobs[0]['runner_job_id'] == 'SW10-S2-B4-PREFLIGHT':
        from tr_platform.research.swing10_s2_b4_preflight import FILES
    elif jobs[0]['runner_job_id'] == 'SW10-S2-B3':
        from tr_platform.research.swing10_s2_b3 import FILES
    elif jobs[0]['runner_job_id'] == 'SW10-S2-B3-CONTINUOUS-PREFLIGHT':
        from tr_platform.research.swing10_s2_b3_continuous_preflight import FILES
    elif jobs[0]['runner_job_id'] == 'SW10-S2-B3-PREFLIGHT':
        from tr_platform.research.swing10_s2_b3_preflight import FILES
    else:
        from tr_platform.research.swing10_s2_b2 import FILES
    result = run(a.job_id, list(FILES))
    if result['count'] != len(FILES):
        raise RuntimeError('SW10 must register/read back every required output')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
