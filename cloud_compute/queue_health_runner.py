from __future__ import annotations

import json
import os

from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.queue_health import snapshot
from cloud_compute.queue_health_history import persist_snapshot


def main() -> int:
    url, key = os.environ.get('SUPABASE_URL'), os.environ.get('SUPABASE_SECRET_KEY')
    if not url or not key:
        raise RuntimeError('SUPABASE_URL and SUPABASE_SECRET_KEY are required')
    config = ControlPlaneConfig(url, key)
    result = snapshot(config)
    persisted = persist_snapshot(
        config,
        result,
        source_execution_id=os.environ.get('GITHUB_RUN_ID'),
    )
    output = dict(result)
    output['persistence'] = {
        'snapshot_id': str(persisted['snapshot_id']),
        'source_execution_id': os.environ.get('GITHUB_RUN_ID'),
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
