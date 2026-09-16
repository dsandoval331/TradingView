from unittest.mock import patch

import pytest

from cloud_compute.autonomous_loop import run_loop
from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.control_plane_worker import RunOutcome


def _job(**overrides):
    base = {
        "job_id": "job-1",
        "strategy_id": "strategy-1",
        "runner_job_id": "CCP3-PARITY-FIXTURE",
        "project_code": "CLOUD_COMPUTE",
        "phase_code": "CCP-8",
        "preferred_executor": "github_actions",
        "priority": 10,
        "git_sha": "abc123",
        "dataset_version": "CCP8-AUTO-1",
        "parameters_json": {},
    }
    base.update(overrides)
    return base


def test_successful_job_without_autonomy_stops_cleanly() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    outcome = RunOutcome(0, _job(), "attempt-1", 1, "artifact-1")
    with patch("cloud_compute.autonomous_loop.run_one_outcome", return_value=outcome):
        summary = run_loop(config)
    assert summary.processed == 1
    assert summary.succeeded == 1
    assert summary.successors == 0
    assert summary.stopped_reason == "governed_chain_complete"


def test_successful_autonomous_job_creates_one_governed_successor() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    job = _job(parameters_json={
        "autonomy": {
            "enabled": True,
            "max_steps": 2,
            "current_step": 0,
            "require_primary_artifact": True,
            "steps": [{
                "runner_job_id": "CCP3-PARITY-FIXTURE",
                "dataset_version": "CCP8-AUTO-2",
                "phase_code": "CCP-8",
            }],
        }
    })
    first = RunOutcome(0, job, "attempt-1", 1, "artifact-1")
    second = RunOutcome(0, _job(job_id="job-2", parameters_json={
        "autonomy": {
            "enabled": True,
            "max_steps": 2,
            "current_step": 1,
            "require_primary_artifact": True,
            "steps": [{"runner_job_id": "CCP3-PARITY-FIXTURE"}],
        }
    }), "attempt-2", 1, "artifact-2")
    with (
        patch("cloud_compute.autonomous_loop.run_one_outcome", side_effect=[first, second]),
        patch("cloud_compute.autonomous_loop.create_job", return_value={"job_id": "job-2"}) as create_job,
    ):
        summary = run_loop(config)
    assert summary.processed == 2
    assert summary.succeeded == 2
    assert summary.successors == 1
    assert summary.stopped_reason == "governed_chain_complete"
    payload = create_job.call_args.args[1]
    assert payload["git_sha"] == "abc123"
    assert payload["dataset_version"] == "CCP8-AUTO-2"
    assert payload["parameters_json"]["autonomy"]["current_step"] == 1
    assert payload["cloud_run_spend_approved"] is False


def test_failure_retries_only_within_bounded_policy() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    job = _job(parameters_json={
        "retry_policy": {"enabled": True, "max_attempts": 2, "retry_exit_codes": [2]}
    })
    failed = RunOutcome(2, job, "attempt-1", 1, None)
    succeeded = RunOutcome(0, job, "attempt-2", 2, "artifact-2")
    with (
        patch("cloud_compute.autonomous_loop.run_one_outcome", side_effect=[failed, succeeded]),
        patch("cloud_compute.autonomous_loop.update_job", return_value=job) as update_job,
    ):
        summary = run_loop(config)
    assert summary.processed == 2
    assert summary.failed == 1
    assert summary.succeeded == 1
    assert summary.retries == 1
    assert update_job.call_args.args[2]["status"] == "queued"


def test_failure_gate_stops_when_retry_budget_exhausted() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    job = _job(parameters_json={
        "retry_policy": {"enabled": True, "max_attempts": 2, "retry_exit_codes": [2]}
    })
    failed = RunOutcome(2, job, "attempt-2", 2, None)
    with patch("cloud_compute.autonomous_loop.run_one_outcome", return_value=failed):
        summary = run_loop(config)
    assert summary.failed == 1
    assert summary.retries == 0
    assert summary.stopped_reason == "failure_gate"


def test_artifact_gate_blocks_autonomous_successor() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    job = _job(parameters_json={
        "autonomy": {
            "enabled": True,
            "max_steps": 2,
            "current_step": 0,
            "require_primary_artifact": True,
            "steps": [{"runner_job_id": "CCP3-PARITY-FIXTURE"}],
        }
    })
    outcome = RunOutcome(0, job, "attempt-1", 1, None)
    with patch("cloud_compute.autonomous_loop.run_one_outcome", return_value=outcome):
        with pytest.raises(RuntimeError, match="no primary artifact"):
            run_loop(config)


def test_unapproved_cloud_run_successor_is_blocked() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    job = _job(parameters_json={
        "autonomy": {
            "enabled": True,
            "max_steps": 2,
            "current_step": 0,
            "steps": [{
                "runner_job_id": "CCP3-PARITY-FIXTURE",
                "preferred_executor": "cloud_run",
                "cloud_run_spend_approved": False,
            }],
        }
    })
    outcome = RunOutcome(0, job, "attempt-1", 1, "artifact-1")
    with patch("cloud_compute.autonomous_loop.run_one_outcome", return_value=outcome):
        with pytest.raises(RuntimeError, match="spend approval"):
            run_loop(config)
