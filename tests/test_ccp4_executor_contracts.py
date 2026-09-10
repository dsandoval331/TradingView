from __future__ import annotations

import pytest

from cloud_compute.cloud_run_adapter import (
    CloudRunJobSpec,
    build_deploy_command,
    build_execute_command,
)
from cloud_compute.local_worker import run_once
from research_runner import runner


def _spec(**overrides):
    data = {
        "project_id": "demo-project",
        "region": "us-central1",
        "job_name": "trading-research",
        "image": "us-central1-docker.pkg.dev/demo/repo/image@sha256:abc",
        "runner_job_id": "CCP4-REMOTE-FIXTURE",
        "spend_approved": True,
    }
    data.update(overrides)
    return CloudRunJobSpec(**data)


def test_cloud_run_deploy_blocked_without_spend_approval():
    with pytest.raises(PermissionError):
        build_deploy_command(_spec(spend_approved=False))


def test_cloud_run_execute_blocked_without_spend_approval():
    with pytest.raises(PermissionError):
        build_execute_command(_spec(spend_approved=False))


def test_cloud_run_contract_targets_common_run_id_entrypoint():
    cmd = build_deploy_command(_spec())
    assert cmd[:4] == ["gcloud", "run", "jobs", "deploy"]
    assert "-m,research_runner.runner,run-id,CCP4-REMOTE-FIXTURE" in cmd
    assert "--image" in cmd
    assert "--task-timeout" in cmd


def test_cloud_run_execute_contract_waits_for_completion():
    cmd = build_execute_command(_spec())
    assert cmd[:4] == ["gcloud", "run", "jobs", "execute"]
    assert "--wait" in cmd


def test_run_id_rejects_unknown_job():
    assert runner.run_id("DOES-NOT-EXIST") == 2


def test_local_worker_uses_same_runner_job_contract(monkeypatch):
    called = {}

    def fake_run_id(job_id):
        called["job_id"] = job_id
        return 0

    monkeypatch.setattr(runner, "run_id", fake_run_id)
    assert run_once(job_id="CCP4-REMOTE-FIXTURE") == 0
    assert called == {"job_id": "CCP4-REMOTE-FIXTURE"}
