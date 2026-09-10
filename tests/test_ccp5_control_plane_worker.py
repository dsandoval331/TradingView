from unittest.mock import patch

from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.control_plane_worker import run_one


def test_no_eligible_job_is_clean_noop() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    with (
        patch("cloud_compute.control_plane_worker.runner._git_sha", return_value="abc123"),
        patch("cloud_compute.control_plane_worker.claim_job", return_value=None),
    ):
        assert run_one(config) == 0


def test_worker_claims_runs_persists_and_completes_job() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    job = {"job_id": "job-1", "runner_job_id": "CCP3-PARITY-FIXTURE", "git_sha": "abc123"}
    claim = {"job": job, "attempt_id": "attempt-1", "attempt_no": 1}
    artifact = {"artifact_id": "artifact-1"}
    with (
        patch("cloud_compute.control_plane_worker.runner._git_sha", return_value="abc123"),
        patch("cloud_compute.control_plane_worker.claim_job", return_value=claim) as claim_job,
        patch("cloud_compute.control_plane_worker.materialize_job_inputs", return_value=[]),
        patch("cloud_compute.control_plane_worker.runner.run_id", return_value=0) as run_id,
        patch("cloud_compute.control_plane_worker._record_stream_logs") as record_logs,
        patch("cloud_compute.control_plane_worker._persist_runner_artifact", return_value=artifact) as persist_artifact,
        patch("cloud_compute.control_plane_worker.update_job", return_value=job) as update_job,
        patch("cloud_compute.control_plane_worker.update_attempt", return_value={}) as update_attempt,
    ):
        assert run_one(config, external_execution_id="run-99") == 0
    claim_job.assert_called_once_with(config, executor="github_actions", git_sha="abc123", external_execution_id="run-99")
    run_id.assert_called_once_with("CCP3-PARITY-FIXTURE")
    record_logs.assert_called_once()
    persist_artifact.assert_called_once()
    assert update_job.call_args.args[2]["status"] == "succeeded"
    assert update_attempt.call_args.args[2]["status"] == "succeeded"
    assert update_attempt.call_args.args[2]["metadata_json"]["atomic_claim"] is True
    assert update_attempt.call_args.args[2]["metadata_json"]["materialized_input_count"] == 0


def test_worker_exact_job_uses_exact_claim_only() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    job = {"job_id": "job-web", "runner_job_id": "CCP3-PARITY-FIXTURE", "git_sha": "abc123"}
    claim = {"job": job, "attempt_id": "attempt-web", "attempt_no": 1}
    with (
        patch("cloud_compute.control_plane_worker.runner._git_sha", return_value="abc123"),
        patch("cloud_compute.control_plane_worker.claim_job_by_id", return_value=claim) as exact_claim,
        patch("cloud_compute.control_plane_worker.claim_job") as generic_claim,
        patch("cloud_compute.control_plane_worker.materialize_job_inputs", return_value=[]),
        patch("cloud_compute.control_plane_worker.runner.run_id", return_value=0),
        patch("cloud_compute.control_plane_worker._record_stream_logs"),
        patch("cloud_compute.control_plane_worker._persist_runner_artifact", return_value={"artifact_id": "artifact-web"}),
        patch("cloud_compute.control_plane_worker.update_job", return_value=job),
        patch("cloud_compute.control_plane_worker.update_attempt", return_value={}),
    ):
        assert run_one(config, external_execution_id="run-web", exact_job_id="job-web") == 0
    exact_claim.assert_called_once_with(
        config,
        job_id="job-web",
        executor="github_actions",
        git_sha="abc123",
        external_execution_id="run-web",
    )
    generic_claim.assert_not_called()


def test_worker_records_runner_failure() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    job = {"job_id": "job-2", "runner_job_id": "UNKNOWN", "git_sha": "abc123"}
    claim = {"job": job, "attempt_id": "attempt-2", "attempt_no": 2}
    with (
        patch("cloud_compute.control_plane_worker.runner._git_sha", return_value="abc123"),
        patch("cloud_compute.control_plane_worker.claim_job", return_value=claim),
        patch("cloud_compute.control_plane_worker.materialize_job_inputs", return_value=[]),
        patch("cloud_compute.control_plane_worker.runner.run_id", return_value=2),
        patch("cloud_compute.control_plane_worker._record_stream_logs"),
        patch("cloud_compute.control_plane_worker.update_job", return_value=job) as update_job,
        patch("cloud_compute.control_plane_worker.update_attempt", return_value={}) as update_attempt,
    ):
        assert run_one(config) == 2
    assert update_job.call_args.args[2]["status"] == "failed"
    assert update_attempt.call_args.args[2]["exit_code"] == 2
    assert update_attempt.call_args.args[2]["metadata_json"]["atomic_claim"] is True
