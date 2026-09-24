from __future__ import annotations

import json
import os

from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.queue_health import snapshot


def main() -> int:
    url, key = os.environ.get('SUPABASE_URL'), os.environ.get('SUPABASE_SECRET_KEY')
    if not url or not key:
        raise RuntimeError('SUPABASE_URL and SUPABASE_SECRET_KEY are required')
    result = snapshot(ControlPlaneConfig(url, key))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
