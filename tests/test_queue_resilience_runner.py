from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.queue_resilience import ResiliencePolicy
from cloud_compute.queue_resilience_runner import run, wake_via_existing_function

CONFIG = ControlPlaneConfig('https://example.supabase.co', 'test-key')
NOW = datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc)


def test_resilience_policy_does_not_enable_job_requeue() -> None:
    policy = ResiliencePolicy()
    assert policy.max_wakeup_attempts == 5
    assert not hasattr(policy, 'automatic_requeue')


def test_runner_reuses_existing_wakeup_function_with_event_record() -> None:
    event = {'event_id': 'e1', 'job_id': 'j1', 'attempt_count': 0}
    response = Mock(ok=True)
    with patch('cloud_compute.queue_resilience_runner.requests.post', return_value=response) as post:
        wake_via_existing_function(CONFIG, event)
    args, kwargs = post.call_args
    assert args[0] == 'https://example.supabase.co/functions/v1/tr-queue-wakeup-v1'
    assert kwargs['json'] == {'record': event}
    assert kwargs['headers']['Authorization'].startswith('Bearer ')


def test_runner_retries_stale_event_and_only_observes_running_ownership() -> None:
    stale = {
        'event_id': 'e1', 'job_id': 'j1', 'dispatch_status': 'pending', 'attempt_count': 0,
        'created_at': (NOW - timedelta(minutes=3)).isoformat(),
    }
    job = {'job_id': 'j1', 'status': 'running', 'started_at': (NOW - timedelta(minutes=31)).isoformat()}
    attempt = {'attempt_no': 1, 'status': 'running'}
    with (
        patch('cloud_compute.queue_resilience.fetch_wakeup_events', return_value=[stale]),
        patch('cloud_compute.queue_resilience.fetch_running_jobs', return_value=[job]),
        patch('cloud_compute.queue_resilience.fetch_job_attempts', return_value=[attempt]),
        patch('cloud_compute.queue_resilience_runner.wake_via_existing_function') as wake,
        patch('cloud_compute.queue_resilience.datetime') as clock,
    ):
        clock.now.return_value = NOW
        result = run(CONFIG)
    wake.assert_called_once_with(CONFIG, stale)
    assert result['wakeup']['retry'] == 1
    assert result['ownership'] == {'stale_owned_escalate': 1}
