from cloud_compute import queue_health_history as history


def snap(at, alerts=()):
    return {
        'observed_at': at,
        'status': 'attention' if alerts else 'healthy',
        'alerts': list(alerts),
        'queue': {}, 'wakeup': {}, 'running': {}, 'thresholds': {}, 'truncated': False,
    }


def test_snapshot_retry_is_idempotent(monkeypatch):
    inserted = []
    monkeypatch.setattr(history, '_fetch_rows', lambda c, table, params: ([{'snapshot_id': 's1'}] if table == history.SNAPSHOT_TABLE and inserted else []))
    monkeypatch.setattr(history, '_insert_one', lambda c, table, payload: inserted.append((table, payload)) or {'snapshot_id': 's1'})
    monkeypatch.setattr(history, 'reconcile_incidents', lambda *a, **k: None)
    s = snap('2026-09-25T06:00:00+00:00')
    history.persist_snapshot(object(), s)
    history.persist_snapshot(object(), s)
    assert len(inserted) == 1
    assert inserted[0][0] == history.SNAPSHOT_TABLE


def test_attention_opens_incident(monkeypatch):
    inserts = []
    monkeypatch.setattr(history, '_fetch_rows', lambda *a, **k: [])
    monkeypatch.setattr(history, '_insert_one', lambda c, table, payload: inserts.append((table, payload)) or payload)
    history.reconcile_incidents(object(), snap('2026-09-25T06:00:00+00:00', ['oldest_queued_age']), snapshot_id='s1')
    assert len(inserts) == 1
    assert inserts[0][1]['incident_key'] == 'queue_operational_health:oldest_queued_age'
    assert inserts[0][1]['state'] == 'open'


def test_same_snapshot_does_not_double_count_open_incident(monkeypatch):
    updates = []
    current = {'incident_id': 'i1', 'alert_code': 'oldest_queued_age', 'state': 'open', 'observation_count': 3, 'last_snapshot_id': 's1'}
    monkeypatch.setattr(history, '_fetch_rows', lambda *a, **k: [current])
    monkeypatch.setattr(history, '_update_one', lambda *a, **k: updates.append((a, k)))
    history.reconcile_incidents(object(), snap('2026-09-25T06:00:00+00:00', ['oldest_queued_age']), snapshot_id='s1')
    assert updates == []


def test_new_attention_observation_continues_incident(monkeypatch):
    patches = []
    current = {'incident_id': 'i1', 'alert_code': 'oldest_queued_age', 'state': 'open', 'observation_count': 3, 'last_snapshot_id': 's1'}
    monkeypatch.setattr(history, '_fetch_rows', lambda *a, **k: [current])
    monkeypatch.setattr(history, '_update_one', lambda c, table, key, value, patch: patches.append(patch) or patch)
    history.reconcile_incidents(object(), snap('2026-09-25T06:10:00+00:00', ['oldest_queued_age']), snapshot_id='s2')
    assert patches[0]['observation_count'] == 4
    assert patches[0]['state'] if 'state' in patches[0] else 'open' == 'open'


def test_healthy_snapshot_recovers_open_incident(monkeypatch):
    patches = []
    current = {'incident_id': 'i1', 'alert_code': 'oldest_queued_age', 'state': 'open', 'observation_count': 2, 'last_snapshot_id': 's1'}
    monkeypatch.setattr(history, '_fetch_rows', lambda *a, **k: [current])
    monkeypatch.setattr(history, '_update_one', lambda c, table, key, value, patch: patches.append(patch) or patch)
    history.reconcile_incidents(object(), snap('2026-09-25T06:20:00+00:00'), snapshot_id='s3')
    assert patches[0]['state'] == 'recovered'
    assert patches[0]['recovered_at'] == '2026-09-25T06:20:00+00:00'


def test_history_adapter_never_targets_research_state(monkeypatch):
    tables = []
    monkeypatch.setattr(history, '_fetch_rows', lambda c, table, params: tables.append(table) or [])
    monkeypatch.setattr(history, '_insert_one', lambda c, table, payload: tables.append(table) or {'snapshot_id': 's1'})
    monkeypatch.setattr(history, '_update_one', lambda c, table, key, value, patch: tables.append(table) or patch)
    history.persist_snapshot(object(), snap('2026-09-25T06:00:00+00:00', ['exhausted_wakeups']))
    assert set(tables) <= {history.SNAPSHOT_TABLE, history.INCIDENT_TABLE}
