from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from cloud_compute.control_plane import ControlPlaneConfig, create_job

ALLOWED_EXECUTORS = {"github_actions", "cloud_run", "local_windows"}


def _load_request(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = ["runner_job_id", "project_code"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise ValueError(f"missing required request fields: {', '.join(missing)}")
    return payload


def build_job_payload(request: dict[str, Any], *, git_sha: str) -> dict[str, Any]:
    executor = request.get("preferred_executor", "github_actions")
    if executor not in ALLOWED_EXECUTORS:
        raise ValueError(f"unsupported preferred_executor: {executor}")

    spend_approved = bool(request.get("cloud_run_spend_approved", False))
    if executor == "cloud_run" and not spend_approved:
        raise PermissionError("cloud_run submission requires explicit cloud_run_spend_approved=true")

    parameters = dict(request.get("parameters_json") or {})
    parameters.setdefault("submission_source", "github_request_manifest")
    parameters.setdefault("attempt_count", 0)

    return {
        "strategy_id": request.get("strategy_id"),
        "research_run_id": request.get("research_run_id"),
        "runner_job_id": request["runner_job_id"],
        "project_code": request["project_code"],
        "phase_code": request.get("phase_code"),
        "status": "queued",
        "preferred_executor": executor,
        "assigned_executor": None,
        "cloud_run_spend_approved": spend_approved,
        "priority": int(request.get("priority", 100)),
        "git_sha": git_sha,
        "container_image": request.get("container_image"),
        "dataset_version": request.get("dataset_version"),
        "parameters_json": parameters,
    }


def submit_request(config: ControlPlaneConfig, request_path: Path, *, git_sha: str) -> dict[str, Any]:
    request = _load_request(request_path)
    payload = build_job_payload(request, git_sha=git_sha)
    return create_job(config, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit a governed TradingResearch cloud job request to Supabase")
    parser.add_argument("request", type=Path)
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    git_sha = os.environ.get("TR_GIT_SHA") or os.environ.get("GITHUB_SHA")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    if not git_sha:
        raise RuntimeError("TR_GIT_SHA or GITHUB_SHA is required")

    job = submit_request(ControlPlaneConfig(url, key), args.request, git_sha=git_sha)
    print(f"CONTROL_PLANE_JOB_SUBMITTED={job['job_id']}")
    print(f"RUNNER_JOB_ID={job['runner_job_id']}")
    print(f"GIT_SHA={job['git_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
