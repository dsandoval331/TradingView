import json

from cloud_compute import queue_health_observability_runner as runner


def test_runner_emits_operator_model(monkeypatch, capsys):
    monkeypatch.setenv('SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setenv('SUPABASE_SECRET_KEY', 'secret')
    monkeypatch.setattr(runner, 'operational_read_model', lambda config: {
        'current_status': 'healthy',
        'escalation': 'none',
        'provenance': {'source_execution_id': 'run-1'},
        'config_url': config.supabase_url,
    })
    assert runner.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output['current_status'] == 'healthy'
    assert output['config_url'] == 'https://example.supabase.co'


def test_runner_requires_control_plane_credentials(monkeypatch):
    monkeypatch.delenv('SUPABASE_URL', raising=False)
    monkeypatch.delenv('SUPABASE_SECRET_KEY', raising=False)
    try:
        runner.main()
    except RuntimeError as exc:
        assert str(exc) == 'SUPABASE_URL and SUPABASE_SECRET_KEY are required'
    else:
        raise AssertionError('runner should reject missing credentials')
