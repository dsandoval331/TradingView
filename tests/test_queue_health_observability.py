from datetime import datetime, timezone

from cloud_compute import queue_health_observability as obs

NOW = datetime(2026, 9, 27, 22, 0, tzinfo=timezone.utc)


def test_empty_model_is_unknown(monkeypatch):
    monkeypatch.setattr(obs, '_fetch_rows', lambda *a, **k: [])
    model = obs.operational_read_model(object(), now=NOW)
    assert model['current_status'] == 'unknown'
    assert model['escalation'] == 'none'
    assert model['active_incidents'] == []


def test_current_health_and_provenance(monkeypatch):
    snap = {'snapshot_id': 's2', 'observed_at': '2026-09-27T21:59:00+00:00', 'status': 'healthy', 'source_execution_id': 'run2'}
    monkeypatch.setattr(obs, '_fetch_rows', lambda c, table, params: [snap] if table == obs.SNAPSHOT_TABLE else [])
    model = obs.operational_read_model(object(), now=NOW)
    assert model['current_status'] == 'healthy'
    assert model['current_age_seconds'] == 60
    assert model['provenance']['source_execution_id'] == 'run2'
    assert model['provenance']['snapshot_id'] == 's2'


def test_warning_incident_escalates_after_three_observations(monkeypatch):
    snap = {'snapshot_id': 's3', 'observed_at': '2026-09-27T21:59:00+00:00', 'status': 'attention'}
    incident = {'incident_id': 'i1', 'incident_key': 'k', 'alert_code': 'oldest_queued_age', 'state': 'open', 'observation_count': 3, 'first_observed_at': '2026-09-27T21:30:00+00:00', 'last_observed_at': '2026-09-27T21:59:00+00:00', 'last_snapshot_id': 's3'}
    monkeypatch.setattr(obs, '_fetch_rows', lambda c, table, params: [snap] if table == obs.SNAPSHOT_TABLE else [incident])
    model = obs.operational_read_model(object(), now=NOW)
    assert model['escalation'] == 'critical'
    assert model['active_incidents'][0]['severity'] == 'critical'
    assert model['active_incidents'][0]['age_seconds'] == 1800


def test_exhausted_wakeup_is_immediately_critical(monkeypatch):
    snap = {'snapshot_id': 's4', 'observed_at': '2026-09-27T21:59:00+00:00', 'status': 'attention'}
    incident = {'incident_id': 'i2', 'alert_code': 'exhausted_wakeups', 'state': 'open', 'observation_count': 1, 'first_observed_at': '2026-09-27T21:58:00+00:00'}
    monkeypatch.setattr(obs, '_fetch_rows', lambda c, table, params: [snap] if table == obs.SNAPSHOT_TABLE else [incident])
    assert obs.operational_read_model(object(), now=NOW)['escalation'] == 'critical'


def test_recovered_incidents_are_not_active(monkeypatch):
    snap = {'snapshot_id': 's5', 'observed_at': '2026-09-27T21:59:00+00:00', 'status': 'healthy'}
    incident = {'incident_id': 'i3', 'alert_code': 'oldest_queued_age', 'state': 'recovered', 'observation_count': 2}
    monkeypatch.setattr(obs, '_fetch_rows', lambda c, table, params: [snap] if table == obs.SNAPSHOT_TABLE else [incident])
    model = obs.operational_read_model(object(), now=NOW)
    assert model['active_incidents'] == []
    assert model['recovered_incidents'] == [incident]
    assert model['escalation'] == 'none'


def test_read_model_only_reads_health_tables(monkeypatch):
    tables = []
    monkeypatch.setattr(obs, '_fetch_rows', lambda c, table, params: tables.append(table) or [])
    obs.operational_read_model(object(), now=NOW)
    assert set(tables) == {obs.SNAPSHOT_TABLE, obs.INCIDENT_TABLE}
