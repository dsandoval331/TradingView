from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from cloud_compute.control_plane import ControlPlaneConfig, claim_job_by_id, create_job, update_attempt, update_job
from cloud_compute.executor_liveness import github_actions_liveness
from cloud_compute.stale_recovery import decide_stale_recovery, recovery_update

COMPLETED_REFERENCE_RUN_ID = "34559028365"


def main() -> int:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    git_sha = os.environ.get("TR_GIT_SHA") or os.environ.get("GITHUB_SHA")
    repository = os.environ.get("GITHUB_REPOSITORY", "dsandoval331/TradingView")
    token = os.environ.get("GITHUB_TOKEN")
    if not url or not key or not git_sha:
        raise RuntimeError("SUPABASE_URL, SUPABASE_SECRET_KEY, and TR_GIT_SHA/GITHUB_SHA are required")

    config = ControlPlaneConfig(url, key)
    job = create_job(config, {
        "strategy_id": "98f761bf-c6f1-4399-b10e-e299cb332141",
        "runner_job_id": "CCP11-STALE-RECOVERY-CERT",
        "project_code": "CLOUD_COMPUTE",
        "phase_code": "CCP-11",
        "status": "queued",
        "preferred_executor": "github_actions",
        "cloud_run_spend_approved": False,
        "priority": 1,
        "git_sha": git_sha,
        "dataset_version": "CCP11-STALE-RECOVERY-LIVE-V1",
        "parameters_json": {
            "submission_source": "ccp11_stale_recovery_live_cert",
            "purpose": "live executor-liveness stale recovery certification",
            "retry_policy": {"enabled": True, "max_attempts": 2},
            "zero_incremental_spend": True,
        },
    })
    claim = claim_job_by_id(
        config,
        job_id=job["job_id"],
        executor="github_actions",
        git_sha=git_sha,
        external_execution_id=COMPLETED_REFERENCE_RUN_ID,
    )
    if claim is None:
        raise RuntimeError("certification fixture could not be claimed")

    stale_started = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    stale_job = update_job(config, job["job_id"], {"started_at": stale_started, "assigned_at": stale_started})
    update_attempt(config, claim["attempt_id"], {"started_at": stale_started})

    liveness = github_actions_liveness(
        repository=repository,
        run_id=COMPLETED_REFERENCE_RUN_ID,
        token=token,
    )
    if liveness.active is not False:
        raise RuntimeError(f"expected completed reference run to be inactive, got {liveness}")

    decision = decide_stale_recovery(
        stale_job,
        now=datetime.now(timezone.utc),
        stale_after_seconds=3600,
        external_execution_active=liveness.active,
    )
    if decision.action != "requeue":
        raise RuntimeError(f"expected requeue decision, got {decision}")

    recovered = update_job(config, job["job_id"], recovery_update(decision))
    completed = datetime.now(timezone.utc).isoformat()
    update_attempt(config, claim["attempt_id"], {
        "status": "failed",
        "completed_at": completed,
        "exit_code": 1,
        "error_summary": "CCP-11 certification: stale execution confirmed inactive and safely requeued",
        "metadata_json": {
            "stale_recovery_certification": True,
            "liveness_reason": liveness.reason,
            "reference_run_id": COMPLETED_REFERENCE_RUN_ID,
            "decision": decision.action,
        },
    })
    if recovered.get("status") != "queued" or recovered.get("assigned_executor") is not None or recovered.get("started_at") is not None:
        raise RuntimeError(f"recovered job did not return to clean queued state: {recovered}")

    # Certification fixture cleanup: do not leave a runnable synthetic job behind.
    update_job(config, job["job_id"], {
        "status": "cancelled",
        "completed_at": completed,
        "last_error": "CCP-11 stale recovery certification fixture complete",
    })

    print("CCP11_STALE_RECOVERY_LIVE_CERTIFICATION=PASS")
    print(f"JOB_ID={job['job_id']}")
    print(f"REFERENCE_RUN_ID={COMPLETED_REFERENCE_RUN_ID}")
    print(f"LIVENESS_ACTIVE={liveness.active}")
    print(f"LIVENESS_REASON={liveness.reason}")
    print(f"RECOVERY_ACTION={decision.action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
