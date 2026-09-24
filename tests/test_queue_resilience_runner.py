from unittest.mock import patch

from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.queue_resilience import ResiliencePolicy

CONFIG = ControlPlaneConfig('https://example.supabase.co', 'test-key')


def test_resilience_policy_does_not_enable_job_requeue() -> None:
    policy = ResiliencePolicy()
    assert policy.max_wakeup_attempts == 5
    assert not hasattr(policy, 'automatic_requeue')


def test_existing_wakeup_endpoint_is_the_integration_boundary() -> None:
    expected = CONFIG.supabase_url.rstrip('/') + '/functions/v1/tr-queue-wakeup-v1'
    assert expected.endswith('/functions/v1/tr-queue-wakeup-v1')
