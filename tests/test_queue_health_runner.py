import json

from cloud_compute import queue_health_runner as runner


def test_runner_observes_then_persists(monkeypatch, capsys):
    calls = []
    observed = {
        'observed_at': '2026-09-25T14:00:00+00:00',
        'status': 'healthy',
        'alerts': [],
        'queue': {}, 'wakeup': {}, 'running': {}, 'thresholds': {}, 'truncated': False,
    }
    monkeypatch.setenv('SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setenv('SUPABASE_SECRET_KEY', 'secret')
    monkeypatch.setenv('GITHUB_RUN_ID', '12345')
    monkeypatch.setattr(runner, 'snapshot', lambda config: calls.append('snapshot') or observed)
    monkeypatch.setattr(
        runner,
        'persist_snapshot',
        lambda config, result, source_execution_id=None: calls.append(
            ('persist', result, source_execution_id)
        ) or {'snapshot_id': 's1'},
    )

    assert runner.main() == 0
    assert calls[0] == 'snapshot'
    assert calls[1][0] == 'persist'
    assert calls[1][1] is observed
    assert calls[1][2] == '12345'
    output = json.loads(capsys.readouterr().out)
    assert output['persistence']['snapshot_id'] == 's1'
    assert output['persistence']['source_execution_id'] == '12345'


def test_runner_requires_supabase_credentials(monkeypatch):
    monkeypatch.delenv('SUPABASE_URL', raising=False)
    monkeypatch.delenv('SUPABASE_SECRET_KEY', raising=False)
    try:
        runner.main()
    except RuntimeError as exc:
        assert 'SUPABASE_URL and SUPABASE_SECRET_KEY are required' in str(exc)
    else:
        raise AssertionError('runner should reject missing credentials')
