from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CloudRunJobSpec:
    project_id: str
    region: str
    job_name: str
    image: str
    runner_job_id: str
    spend_approved: bool = False
    cpu: str = "1"
    memory: str = "1Gi"
    task_timeout: str = "3600s"


def build_deploy_command(spec: CloudRunJobSpec) -> list[str]:
    """Return a declarative gcloud command without executing or provisioning anything.

    The command is intentionally blocked unless spend_approved=True so Cloud Run cannot
    be activated by code paths that have not passed the project cost gate.
    """
    if not spec.spend_approved:
        raise PermissionError(
            "Cloud Run deployment blocked: explicit spend approval is required"
        )
    if not all([spec.project_id, spec.region, spec.job_name, spec.image, spec.runner_job_id]):
        raise ValueError("Cloud Run job spec is incomplete")

    return [
        "gcloud",
        "run",
        "jobs",
        "deploy",
        spec.job_name,
        "--project",
        spec.project_id,
        "--region",
        spec.region,
        "--image",
        spec.image,
        "--cpu",
        spec.cpu,
        "--memory",
        spec.memory,
        "--task-timeout",
        spec.task_timeout,
        "--command",
        "python",
        "--args",
        f"-m,research_runner.runner,run-id,{spec.runner_job_id}",
    ]


def build_execute_command(spec: CloudRunJobSpec) -> list[str]:
    """Return the Cloud Run execution command, guarded by the same spend approval."""
    if not spec.spend_approved:
        raise PermissionError(
            "Cloud Run execution blocked: explicit spend approval is required"
        )
    return [
        "gcloud",
        "run",
        "jobs",
        "execute",
        spec.job_name,
        "--project",
        spec.project_id,
        "--region",
        spec.region,
        "--wait",
    ]
