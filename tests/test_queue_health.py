from datetime import datetime, timezone

from cloud_compute import queue_health


NOW = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)


def test_healthy_empty_control_plane(monkeypatch):
    monkeypatch.setattr(queue_health, '_fetch_rows', lambda *args, **kwargs: [])
    result = queue_health.snapshot(object(), now=NOW)
    assert result['status'] == 'healthy'
    assert result['alerts'] == []
    assert result['queue']['queued_count'] == 0
    assert result['wakeup']['open_count'] == 0
    assert result['running']['stale_count'] == 0


def test_attention_for_old_queue_exhausted_wakeup_and_stale_running(monkeypatch):
    def fake_fetch(config, table, params):
        if table == 'research_jobs' and params.get('status') == 'eq.queued':
            return [{'job_id': 'q1', 'created_at': '2026-09-24T19:50:00+00:00'}]
        if table == 'research_jobs' and params.get('status') == 'eq.running':
            return [{'job_id': 'r1', 'status': 'running', 'started_at': '2026-09-24T19:00:00+00:00'}]
        if table == 'research_queue_wakeup_events':
            return [{'event_id': 'w1', 'dispatch_status': 'failed', 'attempt_count': 5, 'created_at': '2026-09-24T19:40:00+00:00'}]
        raise AssertionError((table, params))

    monkeypatch.setattr(queue_health, '_fetch_rows', fake_fetch)
    monkeypatch.setattr(queue_health, 'fetch_job_attempts', lambda config, job_id: [{'attempt_no': 1, 'status': 'running', 'external_execution_id': 'gh-1'}])
    result = queue_health.snapshot(object(), now=NOW)
    assert result['status'] == 'attention'
    assert set(result['alerts']) == {'oldest_queued_age', 'oldest_open_wakeup_age', 'exhausted_wakeups', 'stale_running_ownership'}
    assert result['queue']['oldest_queued_age_seconds'] == 600
    assert result['wakeup']['exhausted_count'] == 1
    assert result['running']['ownership'] == {'stale_owned_escalate': 1}
    assert result['running']['stale_count'] == 1


def test_observer_uses_reads_only(monkeypatch):
    calls = []
    monkeypatch.setattr(queue_health, '_fetch_rows', lambda config, table, params: calls.append((table, params)) or [])
    queue_health.snapshot(object(), now=NOW)
    assert calls
    assert {table for table, _ in calls} <= {'research_jobs', 'research_queue_wakeup_events'}
