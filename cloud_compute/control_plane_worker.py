from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

from cloud_compute.control_plane import ControlPlaneConfig, create_attempt, fetch_queued_jobs, update_job
from research_runner import runner


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_one(config: ControlPlaneConfig, *, executor: str = "github_actions", external_execution_id: str | None = None) -> int:
    jobs = fetch_queued_jobs(config, limit=20)
    eligible = [
        job for job in jobs
        if job.get("preferred_executor") == executor
        and (job.get("assigned_executor") in {None, executor})
    ]
    if not eligible:
        print("NO_ELIGIBLE_CONTROL_PLANE_JOBS")
        return 0

    job = eligible[0]
    job_id = job["job_id"]
    runner_job_id = job["runner_job_id"]
    attempts = int(job.get("parameters_json", {}).get("attempt_count", 0)) + 1

    update_job(config, job_id, {
        "status": "running",
        "assigned_executor": executor,
        "assigned_at": job.get("assigned_at") or _now(),
        "started_at": _now(),
        "last_error": None,
        "parameters_json": {**job.get("parameters_json", {}), "attempt_count": attempts},
    })
    attempt = create_attempt(config, {
        "job_id": job_id,
        "attempt_no": attempts,
        "executor": executor,
        "external_execution_id": external_execution_id,
        "status": "running",
        "git_sha": job["git_sha"],
        "metadata_json": {"runner_job_id": runner_job_id},
    })

    rc = runner.run_id(runner_job_id)
    completed = _now()
    attempt_id = attempt["attempt_id"]
    if rc == 0:
        update_job(config, job_id, {"status": "succeeded", "completed_at": completed})
        _update_attempt(config, attempt_id, {"status": "succeeded", "completed_at": completed, "exit_code": 0})
        print(f"CONTROL_PLANE_JOB_SUCCEEDED={job_id}")
        return 0

    error = f"research_runner returned exit code {rc}"
    update_job(config, job_id, {"status": "failed", "completed_at": completed, "last_error": error})
    _update_attempt(config, attempt_id, {"status": "failed", "completed_at": completed, "exit_code": rc, "error_summary": error})
    print(f"CONTROL_PLANE_JOB_FAILED={job_id}")
    return rc


def _update_attempt(config: ControlPlaneConfig, attempt_id: str, patch: dict) -> dict:
    import requests
    from cloud_compute.control_plane import _request_headers

    response = requests.patch(
        f"{config.rest_url}/research_job_attempts",
        headers=_request_headers(config.secret_key, prefer="return=representation"),
        params={"attempt_id": f"eq.{attempt_id}"},
        json=patch,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"update_attempt failed: HTTP {response.status_code} {response.text[:500]}")
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("update_attempt expected exactly one returned row")
    return rows[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute one queued TradingResearch control-plane job")
    parser.add_argument("--executor", default="github_actions")
    parser.add_argument("--external-execution-id", default=os.environ.get("GITHUB_RUN_ID"))
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    return run_one(ControlPlaneConfig(url, key), executor=args.executor, external_execution_id=args.external_execution_id)


if __name__ == "__main__":
    raise SystemExit(main())
