from pathlib import Path
from unittest.mock import patch

import pytest

from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.submit_job import build_job_payload, submit_request


def test_build_job_payload_defaults_to_github_and_preserves_git_sha() -> None:
    payload = build_job_payload(
        {"runner_job_id": "CCP3-PARITY-FIXTURE", "project_code": "CLOUD_COMPUTE"},
        git_sha="abc123",
    )
    assert payload["status"] == "queued"
    assert payload["preferred_executor"] == "github_actions"
    assert payload["cloud_run_spend_approved"] is False
    assert payload["git_sha"] == "abc123"
    assert payload["parameters_json"]["submission_source"] == "github_request_manifest"


def test_cloud_run_requires_explicit_spend_approval() -> None:
    with pytest.raises(PermissionError):
        build_job_payload(
            {
                "runner_job_id": "CCP3-PARITY-FIXTURE",
                "project_code": "CLOUD_COMPUTE",
                "preferred_executor": "cloud_run",
            },
            git_sha="abc123",
        )


def test_submit_request_creates_control_plane_job(tmp_path: Path) -> None:
    request = tmp_path / "request.json"
    request.write_text(
        '{"runner_job_id":"CCP3-PARITY-FIXTURE","project_code":"CLOUD_COMPUTE","phase_code":"CCP-7","dataset_version":"CCP7-CERT-1"}',
        encoding="utf-8",
    )
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    with patch("cloud_compute.submit_job.create_job", return_value={"job_id": "job-7", "runner_job_id": "CCP3-PARITY-FIXTURE"}) as create_job:
        row = submit_request(config, request, git_sha="sha-7")
    assert row["job_id"] == "job-7"
    sent = create_job.call_args.args[1]
    assert sent["git_sha"] == "sha-7"
    assert sent["phase_code"] == "CCP-7"
    assert sent["dataset_version"] == "CCP7-CERT-1"
