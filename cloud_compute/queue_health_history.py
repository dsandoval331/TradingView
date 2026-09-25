from __future__ import annotations

from datetime import datetime
from typing import Any

from cloud_compute.control_plane import ControlPlaneConfig, _fetch_rows, _insert_one, _update_one

SNAPSHOT_TABLE = 'research_queue_health_snapshots'
INCIDENT_TABLE = 'research_queue_health_incidents'
SOURCE = 'queue_operational_health_v2'


def _incident_key(alert_code: str) -> str:
    return f'queue_operational_health:{alert_code}'


def persist_snapshot(
    config: ControlPlaneConfig,
    snapshot: dict[str, Any],
    *,
    source_execution_id: str | None = None,
) -> dict[str, Any]:
    """Persist one immutable observation, then reconcile incident lifecycle.

    This adapter writes only Operational Health v2 tables. It never mutates
    research_jobs, research_job_attempts, or queue wake-up state.
    """
    observed_at = str(snapshot['observed_at'])
    existing = _fetch_rows(config, SNAPSHOT_TABLE, {
        'source': f'eq.{SOURCE}',
        'observed_at': f'eq.{observed_at}',
        'limit': '2',
    })
    if len(existing) > 1:
        raise RuntimeError('health snapshot identity is not unique')
    if existing:
        row = existing[0]
    else:
        row = _insert_one(config, SNAPSHOT_TABLE, {
            'observed_at': observed_at,
            'status': str(snapshot['status']),
            'alerts': list(snapshot.get('alerts') or []),
            'snapshot_json': snapshot,
            'source': SOURCE,
            'source_execution_id': source_execution_id,
        })
    reconcile_incidents(config, snapshot, snapshot_id=str(row['snapshot_id']))
    return row


def reconcile_incidents(config: ControlPlaneConfig, snapshot: dict[str, Any], *, snapshot_id: str) -> None:
    observed_at = str(snapshot['observed_at'])
    active_alerts = {str(a) for a in snapshot.get('alerts') or []}
    rows = _fetch_rows(config, INCIDENT_TABLE, {'order': 'created_at.asc', 'limit': '500'})
    by_alert = {str(r['alert_code']): r for r in rows}

    for alert_code in sorted(active_alerts):
        current = by_alert.get(alert_code)
        if current is None:
            _insert_one(config, INCIDENT_TABLE, {
                'incident_key': _incident_key(alert_code),
                'alert_code': alert_code,
                'state': 'open',
                'first_observed_at': observed_at,
                'last_observed_at': observed_at,
                'observation_count': 1,
                'last_snapshot_id': snapshot_id,
                'details_json': {'latest_status': snapshot.get('status')},
            })
        elif str(current.get('state')) == 'open' and str(current.get('last_snapshot_id')) != snapshot_id:
            _update_one(config, INCIDENT_TABLE, 'incident_id', str(current['incident_id']), {
                'last_observed_at': observed_at,
                'observation_count': int(current.get('observation_count') or 0) + 1,
                'last_snapshot_id': snapshot_id,
                'details_json': {'latest_status': snapshot.get('status')},
                'updated_at': observed_at,
            })
        elif str(current.get('state')) == 'recovered':
            _update_one(config, INCIDENT_TABLE, 'incident_id', str(current['incident_id']), {
                'state': 'open',
                'first_observed_at': observed_at,
                'last_observed_at': observed_at,
                'recovered_at': None,
                'observation_count': 1,
                'last_snapshot_id': snapshot_id,
                'details_json': {'latest_status': snapshot.get('status')},
                'updated_at': observed_at,
            })

    for alert_code, current in by_alert.items():
        if alert_code in active_alerts or str(current.get('state')) != 'open':
            continue
        _update_one(config, INCIDENT_TABLE, 'incident_id', str(current['incident_id']), {
            'state': 'recovered',
            'last_observed_at': observed_at,
            'recovered_at': observed_at,
            'last_snapshot_id': snapshot_id,
            'details_json': {'latest_status': snapshot.get('status')},
            'updated_at': observed_at,
        })
