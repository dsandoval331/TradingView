from __future__ import annotations

import argparse
import io
import mimetypes
import os
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from cloud_compute.control_plane import (
    ControlPlaneConfig,
    create_artifact,
    create_attempt,
    create_log,
    fetch_queued_jobs,
    update_attempt,
    update_job,
)
from cloud_compute.manifest import sha256_file
from cloud_compute.storage_poc import _upload_object
from research_runner import runner

DEFAULT_ARTIFACT_BUCKET = "trading-research-market-data"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_stream_logs(
    config: ControlPlaneConfig,
    *,
    job_id: str,
    attempt_id: str,
    stdout_text: str,
    stderr_text: str,
) -> None:
    sequence = 1
    for level, source, text in (
        ("INFO", "runner_stdout", stdout_text),
        ("ERROR", "runner_stderr", stderr_text),
    ):
        for line in text.splitlines():
            message = line.strip()
            if not message:
                continue
            create_log(config, {
                "job_id": job_id,
                "attempt_id": attempt_id,
                "sequence_no": sequence,
                "level": level,
                "source": source,
                "message": message[:4000],
                "metadata_json": {},
            })
            sequence += 1


def _persist_runner_artifact(
    config: ControlPlaneConfig,
    *,
    job_id: str,
    attempt_id: str,
    runner_job_id: str,
    bucket: str,
) -> dict | None:
    state = runner._load_state()
    result = state.get("jobs", {}).get(runner_job_id, {}).get("result") or {}
    rel = result.get("artifact")
    if not rel:
        return None

    root = runner.WORK_ROOT.resolve()
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"artifact path escapes work root: {rel}") from exc
    if not path.is_file():
        raise RuntimeError(f"declared artifact does not exist: {rel}")

    digest = sha256_file(path)
    expected = result.get("sha256")
    if expected and expected != digest:
        raise RuntimeError(f"artifact checksum mismatch for {rel}")

    object_path = f"artifacts/{job_id}/{attempt_id}/{path.name}"
    _upload_object(
        config.supabase_url,
        config.secret_key,
        bucket,
        object_path,
        path,
        allow_existing=False,
    )
    return create_artifact(config, {
        "job_id": job_id,
        "attempt_id": attempt_id,
        "artifact_type": "research_output",
        "storage_backend": "supabase_storage",
        "bucket_name": bucket,
        "object_path": object_path,
        "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "size_bytes": path.stat().st_size,
        "sha256": digest,
        "is_primary": True,
        "metadata_json": {
            "runner_job_id": runner_job_id,
            "runner_relative_path": rel,
        },
    })


def run_one(
    config: ControlPlaneConfig,
    *,
    executor: str = "github_actions",
    external_execution_id: str | None = None,
    artifact_bucket: str = DEFAULT_ARTIFACT_BUCKET,
) -> int:
    jobs = fetch_queued_jobs(config, limit=20)
    actual_git_sha = runner._git_sha()
    eligible = [
        job for job in jobs
        if job.get("preferred_executor") == executor
        and (job.get("assigned_executor") in {None, executor})
        and job.get("git_sha") == actual_git_sha
    ]
    if not eligible:
        mismatched = [
            job for job in jobs
            if job.get("preferred_executor") == executor
            and (job.get("assigned_executor") in {None, executor})
            and job.get("git_sha") != actual_git_sha
        ]
        if mismatched:
            print(f"NO_MATCHING_GIT_SHA queued={mismatched[0].get('git_sha')} actual={actual_git_sha}")
        else:
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
    attempt_id = attempt["attempt_id"]

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            rc = runner.run_id(runner_job_id)
        _record_stream_logs(
            config,
            job_id=job_id,
            attempt_id=attempt_id,
            stdout_text=stdout_buffer.getvalue(),
            stderr_text=stderr_buffer.getvalue(),
        )

        completed = _now()
        if rc == 0:
            artifact = _persist_runner_artifact(
                config,
                job_id=job_id,
                attempt_id=attempt_id,
                runner_job_id=runner_job_id,
                bucket=artifact_bucket,
            )
            update_job(config, job_id, {"status": "succeeded", "completed_at": completed})
            update_attempt(config, attempt_id, {
                "status": "succeeded",
                "completed_at": completed,
                "exit_code": 0,
                "metadata_json": {
                    "runner_job_id": runner_job_id,
                    "artifact_id": artifact.get("artifact_id") if artifact else None,
                },
            })
            print(f"CONTROL_PLANE_JOB_SUCCEEDED={job_id}")
            return 0

        error = f"research_runner returned exit code {rc}"
        update_job(config, job_id, {"status": "failed", "completed_at": completed, "last_error": error})
        update_attempt(config, attempt_id, {
            "status": "failed",
            "completed_at": completed,
            "exit_code": rc,
            "error_summary": error,
        })
        print(f"CONTROL_PLANE_JOB_FAILED={job_id}")
        return rc
    except Exception as exc:
        completed = _now()
        error = f"worker persistence failure: {exc}"
        update_job(config, job_id, {"status": "failed", "completed_at": completed, "last_error": error})
        update_attempt(config, attempt_id, {
            "status": "failed",
            "completed_at": completed,
            "exit_code": 1,
            "error_summary": error,
        })
        print(f"CONTROL_PLANE_JOB_FAILED={job_id}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute one queued TradingResearch control-plane job")
    parser.add_argument("--executor", default="github_actions")
    parser.add_argument("--external-execution-id", default=os.environ.get("GITHUB_RUN_ID"))
    parser.add_argument("--artifact-bucket", default=os.environ.get("TR_ARTIFACT_BUCKET", DEFAULT_ARTIFACT_BUCKET))
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    return run_one(
        ControlPlaneConfig(url, key),
        executor=args.executor,
        external_execution_id=args.external_execution_id,
        artifact_bucket=args.artifact_bucket,
    )


if __name__ == "__main__":
    raise SystemExit(main())
