from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cloud_compute.control_plane import ControlPlaneConfig, _fetch_rows
from cloud_compute.queue_health_history import INCIDENT_TABLE, SNAPSHOT_TABLE, SOURCE

SEVERITY_BY_ALERT = {
    'oldest_queued_age': 'warning',
    'oldest_open_wakeup_age': 'warning',
    'exhausted_wakeups': 'critical',
    'stale_running_ownership': 'critical',
}


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace('Z', '+00:00')
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _age_seconds(value: Any, now: datetime) -> int | None:
    dt = _parse_dt(value)
    return None if dt is None else max(0, int((now - dt).total_seconds()))


def incident_severity(alert_code: str, observation_count: int = 1) -> str:
    base = SEVERITY_BY_ALERT.get(alert_code, 'warning')
    if base == 'warning' and observation_count >= 3:
        return 'critical'
    return base


def operational_read_model(
    config: ControlPlaneConfig,
    *,
    now: datetime | None = None,
    snapshot_limit: int = 50,
    incident_limit: int = 100,
) -> dict[str, Any]:
    """Build a read-only current/history/incident model for operators and UI."""
    now = now or datetime.now(timezone.utc)
    snapshots = _fetch_rows(config, SNAPSHOT_TABLE, {
        'source': f'eq.{SOURCE}', 'order': 'observed_at.desc', 'limit': str(snapshot_limit),
    })
    incidents = _fetch_rows(config, INCIDENT_TABLE, {
        'order': 'updated_at.desc', 'limit': str(incident_limit),
    })
    current = snapshots[0] if snapshots else None
    active = [r for r in incidents if str(r.get('state')) == 'open']
    recovered = [r for r in incidents if str(r.get('state')) == 'recovered']

    active_view = []
    for row in active:
        count = int(row.get('observation_count') or 0)
        alert = str(row.get('alert_code') or 'unknown')
        active_view.append({
            'incident_id': row.get('incident_id'),
            'incident_key': row.get('incident_key'),
            'alert_code': alert,
            'severity': incident_severity(alert, count),
            'observation_count': count,
            'first_observed_at': row.get('first_observed_at'),
            'last_observed_at': row.get('last_observed_at'),
            'age_seconds': _age_seconds(row.get('first_observed_at'), now),
            'last_snapshot_id': row.get('last_snapshot_id'),
        })

    status = 'unknown' if current is None else str(current.get('status') or 'unknown')
    if any(r['severity'] == 'critical' for r in active_view):
        escalation = 'critical'
    elif active_view:
        escalation = 'warning'
    else:
        escalation = 'none'

    return {
        'generated_at': now.isoformat(),
        'current': current,
        'current_status': status,
        'current_age_seconds': _age_seconds(current.get('observed_at'), now) if current else None,
        'snapshot_count_returned': len(snapshots),
        'history': snapshots,
        'active_incidents': active_view,
        'recovered_incidents': recovered,
        'escalation': escalation,
        'provenance': {
            'source': SOURCE,
            'source_execution_id': current.get('source_execution_id') if current else None,
            'snapshot_id': current.get('snapshot_id') if current else None,
        },
    }
