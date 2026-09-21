from __future__ import annotations

from unittest.mock import Mock, patch

from cloud_compute.control_plane import (
    ControlPlaneConfig,
    _request_headers,
    claim_job,
    create_attempt,
    create_job,
    fetch_queued_jobs,
    update_job,
)


def test_modern_secret_key_is_not_used_as_bearer() -> None:
    headers = _request_headers('sb_secret_example')
    assert headers['apikey'] == 'sb_secret_example'
    assert 'Authorization' not in headers


def test_create_job_posts_and_returns_single_row() -> None:
    config = ControlPlaneConfig('https://example.supabase.co', 'sb_secret_example')
    response = Mock(ok=True)
    response.json.return_value = [{'job_id': 'job-1', 'status': 'queued'}]
    with patch('cloud_compute.control_plane.requests.post', return_value=response) as post:
        row = create_job(config, {'runner_job_id': 'CCP4-REMOTE-FIXTURE'})
    assert row['job_id'] == 'job-1'
    assert post.call_args.kwargs['headers']['Prefer'] == 'return=representation'


def test_fetch_queued_jobs_orders_priority_then_time() -> None:
    config = ControlPlaneConfig('https://example.supabase.co', 'legacy.jwt')
    response = Mock(ok=True)
    response.json.return_value = [{'job_id': 'a'}]
    with patch('cloud_compute.control_plane.requests.get', return_value=response) as get:
        rows = fetch_queued_jobs(config, limit=7)
    assert rows == [{'job_id': 'a'}]
    params = get.call_args.kwargs['params']
    assert params['status'] == 'in.(queued,local_pending)'
    assert params['order'] == 'priority.asc,queued_at.asc'
    assert params['limit'] == '7'


def test_claim_job_calls_atomic_rpc() -> None:
    config = ControlPlaneConfig('https://example.supabase.co', 'sb_secret_example')
    response = Mock(ok=True)
    response.json.return_value = {
        'job': {'job_id': 'job-8', 'runner_job_id': 'CCP3-PARITY-FIXTURE'},
        'attempt_id': 'attempt-8',
        'attempt_no': 1,
    }
    with patch('cloud_compute.control_plane.requests.post', return_value=response) as post:
        claim = claim_job(config, executor='github_actions', git_sha='sha-8', external_execution_id='run-8')
    assert claim['attempt_id'] == 'attempt-8'
    assert post.call_args.args[0].endswith('/rpc/claim_research_job_v1')
    assert post.call_args.kwargs['json'] == {
        'p_executor': 'github_actions',
        'p_git_sha': 'sha-8',
        'p_external_execution_id': 'run-8',
    }


def test_claim_job_allows_empty_queue() -> None:
    config = ControlPlaneConfig('https://example.supabase.co', 'sb_secret_example')
    response = Mock(ok=True)
    response.json.return_value = None
    with patch('cloud_compute.control_plane.requests.post', return_value=response):
        assert claim_job(config, executor='github_actions', git_sha='sha-8') is None


def test_update_job_uses_job_id_filter() -> None:
    config = ControlPlaneConfig('https://example.supabase.co', 'sb_secret_example')
    response = Mock(ok=True)
    response.json.return_value = [{'job_id': 'job-1', 'status': 'running'}]
    with patch('cloud_compute.control_plane.requests.patch', return_value=response) as patch_req:
        row = update_job(config, 'job-1', {'status': 'running'})
    assert row['status'] == 'running'
    assert patch_req.call_args.kwargs['params'] == {'job_id': 'eq.job-1'}


def test_create_attempt_targets_attempt_table() -> None:
    config = ControlPlaneConfig('https://example.supabase.co', 'sb_secret_example')
    response = Mock(ok=True)
    response.json.return_value = [{'attempt_id': 'attempt-1'}]
    with patch('cloud_compute.control_plane.requests.post', return_value=response) as post:
        row = create_attempt(config, {'job_id': 'job-1', 'attempt_no': 1})
    assert row['attempt_id'] == 'attempt-1'
    assert post.call_args.args[0].endswith('/research_job_attempts')
