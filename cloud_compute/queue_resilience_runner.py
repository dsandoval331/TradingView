from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import requests

from cloud_compute.control_plane import ControlPlaneConfig, _request_headers
from cloud_compute.queue_resilience import ResiliencePolicy, reconcile_running_jobs, reconcile_wakeup_events


def wake_via_existing_function(config: ControlPlaneConfig, event: dict[str, Any]) -> None:
    endpoint = config.supabase_url.rstrip('/') + '/functions/v1/tr-queue-wakeup-v1'
    response = requests.post(endpoint, headers=_request_headers(config.secret_key), json={'record': event}, timeout=30)
    if not response.ok:
        raise RuntimeError(f'wakeup function failed: HTTP {response.status_code} {response.text[:500]}')


def run(
    config: ControlPlaneConfig,
    *,
    limit: int = 100,
    now: datetime | None = None,
    policy: ResiliencePolicy | None = None,
) -> dict[str, Any]:
    wakeup = reconcile_wakeup_events(
        config, wake=lambda event: wake_via_existing_function(config, event), limit=limit, now=now, policy=policy
    )
    ownership = reconcile_running_jobs(config, limit=limit, now=now, policy=policy)
    return {'wakeup': wakeup, 'ownership': ownership}


def main() -> int:
    url, key = os.environ.get('SUPABASE_URL'), os.environ.get('SUPABASE_SECRET_KEY')
    if not url or not key:
        raise RuntimeError('SUPABASE_URL and SUPABASE_SECRET_KEY are required')
    print(json.dumps(run(ControlPlaneConfig(url, key)), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
