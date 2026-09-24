from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from cloud_compute.control_plane import ControlPlaneConfig, _fetch_rows
from cloud_compute.queue_resilience import ResiliencePolicy, _dt, evaluate_running_job_ownership, fetch_job_attempts


@dataclass(frozen=True)
class HealthThresholds:
    queued_warn_after_seconds: int = 300
    wakeup_warn_after_seconds: int = 300
    exhausted_wakeup_count_warn: int = 1
    stale_running_count_warn: int = 1


def _age_seconds(value: Any, now: datetime) -> int | None:
    dt = _dt(value)
    return None if dt is None else max(0, int((now - dt).total_seconds()))


def snapshot(config: ControlPlaneConfig, *, now: datetime | None = None, limit: int = 500) -> dict[str, Any]:
    """Return a read-only operational snapshot. Never mutates research state."""
    now = now or datetime.now(timezone.utc)
    policy = ResiliencePolicy()
    thresholds = HealthThresholds()

    queued = _fetch_rows(config, 'research_jobs', {'status': 'eq.queued', 'order': 'created_at.asc', 'limit': str(limit)})
    running = _fetch_rows(config, 'research_jobs', {'status': 'eq.running', 'order': 'started_at.asc', 'limit': str(limit)})
    wakeups = _fetch_rows(config, 'research_queue_wakeup_events', {'order': 'created_at.asc', 'limit': str(limit)})

    open_wakeups = [r for r in wakeups if str(r.get('dispatch_status') or '') in {'pending', 'requested', 'failed'}]
    exhausted = [r for r in open_wakeups if int(r.get('attempt_count') or 0) >= policy.max_wakeup_attempts]
    failed = [r for r in open_wakeups if str(r.get('dispatch_status') or '') == 'failed']

    ownership: dict[str, int] = {}
    for job in running:
        action = evaluate_running_job_ownership(job, fetch_job_attempts(config, str(job['job_id'])), now=now, policy=policy)
        ownership[action] = ownership.get(action, 0) + 1

    oldest_queued = max((_age_seconds(r.get('created_at'), now) or 0 for r in queued), default=0)
    oldest_wakeup = max((_age_seconds(r.get('created_at'), now) or 0 for r in open_wakeups), default=0)
    stale_running = sum(v for k, v in ownership.items() if k.startswith('stale_'))

    alerts: list[str] = []
    if oldest_queued >= thresholds.queued_warn_after_seconds:
        alerts.append('oldest_queued_age')
    if oldest_wakeup >= thresholds.wakeup_warn_after_seconds:
        alerts.append('oldest_open_wakeup_age')
    if len(exhausted) >= thresholds.exhausted_wakeup_count_warn:
        alerts.append('exhausted_wakeups')
    if stale_running >= thresholds.stale_running_count_warn:
        alerts.append('stale_running_ownership')

    return {
        'observed_at': now.isoformat(),
        'status': 'healthy' if not alerts else 'attention',
        'alerts': alerts,
        'thresholds': asdict(thresholds),
        'queue': {'queued_count': len(queued), 'oldest_queued_age_seconds': oldest_queued},
        'wakeup': {
            'open_count': len(open_wakeups),
            'failed_count': len(failed),
            'exhausted_count': len(exhausted),
            'oldest_open_age_seconds': oldest_wakeup,
            'total_attempts_open': sum(int(r.get('attempt_count') or 0) for r in open_wakeups),
        },
        'running': {'count': len(running), 'ownership': ownership, 'stale_count': stale_running},
        'truncated': len(queued) >= limit or len(running) >= limit or len(wakeups) >= limit,
    }
