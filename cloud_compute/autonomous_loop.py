from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

from cloud_compute.control_plane import ControlPlaneConfig, create_job, update_job
from cloud_compute.control_plane_worker import RunOutcome, run_one_outcome

HARD_MAX_JOBS_PER_RUN = 25
HARD_MAX_CHAIN_STEPS = 10
HARD_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class LoopSummary:
    processed: int
    succeeded: int
    failed: int
    retries: int
    successors: int
    stopped_reason: str


def _autonomy(job: dict[str, Any]) -> dict[str, Any]:
    params = job.get("parameters_json") or {}
    value = params.get("autonomy") or {}
    return value if isinstance(value, dict) else {}


def _retry_policy(job: dict[str, Any]) -> dict[str, Any]:
    params = job.get("parameters_json") or {}
    value = params.get("retry_policy") or {}
    return value if isinstance(value, dict) else {}


def _validate_autonomy(job: dict[str, Any]) -> tuple[bool, str]:
    autonomy = _autonomy(job)
    if not autonomy.get("enabled", False):
        return False, "autonomy_disabled"

    max_steps = int(autonomy.get("max_steps", 1))
    current_step = int(autonomy.get("current_step", 0))
    steps = autonomy.get("steps") or []
    if max_steps < 1 or max_steps > HARD_MAX_CHAIN_STEPS:
        raise RuntimeError(f"autonomy max_steps must be between 1 and {HARD_MAX_CHAIN_STEPS}")
    if current_step < 0 or current_step >= max_steps:
        raise RuntimeError("autonomy current_step is outside the governed range")
    if not isinstance(steps, list):
        raise RuntimeError("autonomy steps must be a list")
    if len(steps) > HARD_MAX_CHAIN_STEPS - 1:
        raise RuntimeError("autonomy steps exceeds hard chain limit")
    return True, "enabled"


def _schedule_retry(config: ControlPlaneConfig, outcome: RunOutcome) -> bool:
    if outcome.job is None or outcome.exit_code == 0:
        return False
    policy = _retry_policy(outcome.job)
    if not policy.get("enabled", False):
        return False

    max_attempts = int(policy.get("max_attempts", 1))
    if max_attempts < 1 or max_attempts > HARD_MAX_ATTEMPTS:
        raise RuntimeError(f"retry max_attempts must be between 1 and {HARD_MAX_ATTEMPTS}")
    retry_codes = policy.get("retry_exit_codes")
    if retry_codes is not None:
        if not isinstance(retry_codes, list) or outcome.exit_code not in {int(x) for x in retry_codes}:
            return False
    if outcome.attempt_no >= max_attempts:
        return False

    update_job(config, outcome.job["job_id"], {
        "status": "queued",
        "assigned_executor": None,
        "started_at": None,
        "completed_at": None,
    })
    return True


def _create_successor(config: ControlPlaneConfig, outcome: RunOutcome) -> dict[str, Any] | None:
    if outcome.job is None or outcome.exit_code != 0:
        return None
    enabled, _ = _validate_autonomy(outcome.job)
    if not enabled:
        return None

    autonomy = _autonomy(outcome.job)
    if autonomy.get("require_primary_artifact", True) and not outcome.artifact_id:
        raise RuntimeError("autonomous continuation blocked: successful job has no primary artifact")

    current_step = int(autonomy.get("current_step", 0))
    max_steps = int(autonomy.get("max_steps", 1))
    steps = autonomy.get("steps") or []
    next_index = current_step
    if current_step + 1 >= max_steps or next_index >= len(steps):
        return None

    spec = steps[next_index]
    if not isinstance(spec, dict):
        raise RuntimeError("autonomy successor step must be an object")
    runner_job_id = spec.get("runner_job_id")
    if not isinstance(runner_job_id, str) or not runner_job_id.strip():
        raise RuntimeError("autonomy successor step requires runner_job_id")

    parent_params = dict(outcome.job.get("parameters_json") or {})
    next_autonomy = dict(autonomy)
    next_autonomy["current_step"] = current_step + 1
    next_params = dict(spec.get("parameters_json") or {})
    next_params["autonomy"] = next_autonomy
    if "retry_policy" in parent_params and "retry_policy" not in next_params:
        next_params["retry_policy"] = parent_params["retry_policy"]
    next_params["autonomous_parent_job_id"] = outcome.job["job_id"]

    preferred_executor = spec.get("preferred_executor", outcome.job.get("preferred_executor", "github_actions"))
    spend_approved = bool(spec.get("cloud_run_spend_approved", False))
    if preferred_executor == "cloud_run" and not spend_approved:
        raise RuntimeError("autonomous Cloud Run continuation blocked without explicit spend approval")

    payload = {
        "strategy_id": outcome.job.get("strategy_id"),
        "runner_job_id": runner_job_id,
        "project_code": spec.get("project_code", outcome.job["project_code"]),
        "phase_code": spec.get("phase_code", outcome.job.get("phase_code")),
        "status": "queued",
        "preferred_executor": preferred_executor,
        "cloud_run_spend_approved": spend_approved,
        "priority": int(spec.get("priority", outcome.job.get("priority", 100))),
        "git_sha": outcome.job["git_sha"],
        "dataset_version": spec.get("dataset_version", outcome.job.get("dataset_version")),
        "parameters_json": next_params,
    }
    return create_job(config, payload)


def run_loop(
    config: ControlPlaneConfig,
    *,
    executor: str = "github_actions",
    external_execution_id: str | None = None,
    artifact_bucket: str = "trading-research-market-data",
    max_jobs: int = 10,
) -> LoopSummary:
    if max_jobs < 1 or max_jobs > HARD_MAX_JOBS_PER_RUN:
        raise ValueError(f"max_jobs must be between 1 and {HARD_MAX_JOBS_PER_RUN}")

    processed = succeeded = failed = retries = successors = 0
    stopped_reason = "queue_empty"

    for _ in range(max_jobs):
        outcome = run_one_outcome(
            config,
            executor=executor,
            external_execution_id=external_execution_id,
            artifact_bucket=artifact_bucket,
        )
        if outcome.job is None:
            stopped_reason = "queue_empty"
            break

        processed += 1
        if outcome.exit_code == 0:
            succeeded += 1
            successor = _create_successor(config, outcome)
            if successor is not None:
                successors += 1
                continue
            stopped_reason = "governed_chain_complete"
            break

        failed += 1
        if _schedule_retry(config, outcome):
            retries += 1
            continue
        stopped_reason = "failure_gate"
        break
    else:
        stopped_reason = "run_job_limit"

    summary = LoopSummary(processed, succeeded, failed, retries, successors, stopped_reason)
    print(
        "AUTONOMOUS_LOOP_SUMMARY "
        f"processed={processed} succeeded={succeeded} failed={failed} "
        f"retries={retries} successors={successors} stopped={stopped_reason}"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a governed TradingResearch autonomous cloud job chain")
    parser.add_argument("--executor", default="github_actions")
    parser.add_argument("--external-execution-id", default=os.environ.get("GITHUB_RUN_ID"))
    parser.add_argument("--artifact-bucket", default=os.environ.get("TR_ARTIFACT_BUCKET", "trading-research-market-data"))
    parser.add_argument("--max-jobs", type=int, default=10)
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    summary = run_loop(
        ControlPlaneConfig(url, key),
        executor=args.executor,
        external_execution_id=args.external_execution_id,
        artifact_bucket=args.artifact_bucket,
        max_jobs=args.max_jobs,
    )
    return 1 if summary.stopped_reason in {"failure_gate", "run_job_limit"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
