from unittest.mock import Mock, patch

from cloud_compute.control_plane import ControlPlaneConfig, claim_job_by_id
from cloud_compute.autonomous_loop import run_loop
from cloud_compute.control_plane_worker import RunOutcome


def test_claim_job_by_id_uses_exact_rpc_and_identifiers() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    response = Mock(ok=True)
    response.json.return_value = {
        "job": {"job_id": "job-9"},
        "attempt_id": "attempt-1",
        "attempt_no": 1,
    }
    with patch("cloud_compute.control_plane.requests.post", return_value=response) as post:
        result = claim_job_by_id(
            config,
            job_id="job-9",
            executor="github_actions",
            git_sha="abc123",
            external_execution_id="run-9",
        )
    assert result["job"]["job_id"] == "job-9"
    assert post.call_args.args[0].endswith("/rpc/claim_research_job_by_id_v1")
    assert post.call_args.kwargs["json"] == {
        "p_job_id": "job-9",
        "p_executor": "github_actions",
        "p_git_sha": "abc123",
        "p_external_execution_id": "run-9",
    }


def test_autonomous_loop_pins_first_job_and_successor() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    parent = {
        "job_id": "job-9",
        "strategy_id": "strategy-1",
        "runner_job_id": "CCP3-PARITY-FIXTURE",
        "project_code": "CLOUD_COMPUTE",
        "phase_code": "CCP-9",
        "preferred_executor": "github_actions",
        "priority": 20,
        "git_sha": "abc123",
        "dataset_version": "CCP9-WEB-1",
        "parameters_json": {
            "autonomy": {
                "enabled": True,
                "max_steps": 2,
                "current_step": 0,
                "steps": [{"runner_job_id": "CCP3-PARITY-FIXTURE"}],
            }
        },
    }
    child = {**parent, "job_id": "job-10", "parameters_json": {"autonomy": {"enabled": True, "max_steps": 2, "current_step": 1, "steps": []}}}
    first = RunOutcome(0, parent, "attempt-1", 1, "artifact-1")
    second = RunOutcome(0, child, "attempt-2", 1, "artifact-2")
    with (
        patch("cloud_compute.autonomous_loop.run_one_outcome", side_effect=[first, second]) as run_one,
        patch("cloud_compute.autonomous_loop.create_job", return_value={"job_id": "job-10"}),
    ):
        summary = run_loop(config, first_job_id="job-9")
    assert summary.succeeded == 2
    assert run_one.call_args_list[0].kwargs["exact_job_id"] == "job-9"
    assert run_one.call_args_list[1].kwargs["exact_job_id"] == "job-10"
