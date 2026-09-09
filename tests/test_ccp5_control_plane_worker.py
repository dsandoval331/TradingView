from unittest.mock import Mock, patch

from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.control_plane_worker import run_one


def test_no_eligible_job_is_clean_noop() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    with patch("cloud_compute.control_plane_worker.fetch_queued_jobs", return_value=[]):
        assert run_one(config) == 0


def test_worker_claims_runs_and_completes_job() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    job = {
        "job_id": "job-1",
        "runner_job_id": "CCP3-PARITY-FIXTURE",
        "preferred_executor": "github_actions",
        "assigned_executor": None,
        "assigned_at": None,
        "git_sha": "abc123",
        "parameters_json": {},
    }
    attempt = {"attempt_id": "attempt-1"}
    with (
        patch("cloud_compute.control_plane_worker.fetch_queued_jobs", return_value=[job]),
        patch("cloud_compute.control_plane_worker.update_job", return_value=job) as update_job,
        patch("cloud_compute.control_plane_worker.create_attempt", return_value=attempt),
        patch("cloud_compute.control_plane_worker.runner.run_id", return_value=0) as run_id,
        patch("cloud_compute.control_plane_worker._update_attempt", return_value=attempt) as update_attempt,
    ):
        assert run_one(config, external_execution_id="run-99") == 0
    run_id.assert_called_once_with("CCP3-PARITY-FIXTURE")
    assert update_job.call_args_list[-1].args[2]["status"] == "succeeded"
    assert update_attempt.call_args.args[2]["status"] == "succeeded"


def test_worker_records_runner_failure() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    job = {
        "job_id": "job-2",
        "runner_job_id": "UNKNOWN",
        "preferred_executor": "github_actions",
        "assigned_executor": None,
        "assigned_at": None,
        "git_sha": "abc123",
        "parameters_json": {},
    }
    attempt = {"attempt_id": "attempt-2"}
    with (
        patch("cloud_compute.control_plane_worker.fetch_queued_jobs", return_value=[job]),
        patch("cloud_compute.control_plane_worker.update_job", return_value=job) as update_job,
        patch("cloud_compute.control_plane_worker.create_attempt", return_value=attempt),
        patch("cloud_compute.control_plane_worker.runner.run_id", return_value=2),
        patch("cloud_compute.control_plane_worker._update_attempt", return_value=attempt) as update_attempt,
    ):
        assert run_one(config) == 2
    assert update_job.call_args_list[-1].args[2]["status"] == "failed"
    assert update_attempt.call_args.args[2]["exit_code"] == 2
