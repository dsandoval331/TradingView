import json

from cloud_compute import queue_health_observability_runner as runner


def test_runner_emits_operator_model(monkeypatch, capsys):
    sentinel_config = object()
    monkeypatch.setattr(runner.ControlPlaneConfig, 'from_env', lambda: sentinel_config)
    monkeypatch.setattr(runner, 'operational_read_model', lambda config: {
        'current_status': 'healthy',
        'escalation': 'none',
        'provenance': {'source_execution_id': 'run-1'},
    })
    assert runner.main() == 0
    assert json.loads(capsys.readouterr().out)['current_status'] == 'healthy'
