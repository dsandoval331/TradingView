from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from cloud_compute.control_plane import (
    ControlPlaneConfig,
    claim_job_by_id,
    create_job,
    update_attempt,
    update_job,
)

DEFAULT_WORKERS = 8


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def race_exact_claims(
    config: ControlPlaneConfig,
    *,
    job_id: str,
    git_sha: str,
    workers: int = DEFAULT_WORKERS,
    external_execution_prefix: str = "ccp11-race",
) -> dict[str, Any]:
    if workers < 2:
        raise ValueError("workers must be >= 2")

    def claim(index: int):
        return claim_job_by_id(
            config,
            job_id=job_id,
            executor="github_actions",
            git_sha=git_sha,
            external_execution_id=f"{external_execution_prefix}-{index}",
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(claim, range(workers)))

    winners = [row for row in results if row is not None]
    if len(winners) != 1:
        raise RuntimeError(f"atomic claim violation: expected 1 winner, got {len(winners)}")
    winner = winners[0]
    return {
        "workers": workers,
        "winner_count": 1,
        "null_claim_count": workers - 1,
        "attempt_id": winner["attempt_id"],
        "attempt_no": int(winner.get("attempt_no") or 1),
        "job": winner["job"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Live CCP-11 atomic claim concurrency certification")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    git_sha = os.environ.get("TR_GIT_SHA") or os.environ.get("GITHUB_SHA")
    if not url or not key or not git_sha:
        raise RuntimeError("SUPABASE_URL, SUPABASE_SECRET_KEY, and TR_GIT_SHA/GITHUB_SHA are required")

    config = ControlPlaneConfig(url, key)
    job = create_job(config, {
        "strategy_id": "98f761bf-c6f1-4399-b10e-e299cb332141",
        "runner_job_id": "CCP11-ATOMIC-CLAIM-CERT",
        "project_code": "CLOUD_COMPUTE",
        "phase_code": "CCP-11",
        "status": "queued",
        "preferred_executor": "github_actions",
        "cloud_run_spend_approved": False,
        "priority": 1,
        "git_sha": git_sha,
        "dataset_version": "CCP11-ATOMIC-CLAIM-RACE-V1",
        "parameters_json": {
            "submission_source": "ccp11_concurrency_cert",
            "purpose": "live atomic claim race certification",
            "zero_incremental_spend": True,
        },
    })

    result = race_exact_claims(config, job_id=job["job_id"], git_sha=git_sha, workers=args.workers)
    completed = _now()
    update_job(config, job["job_id"], {
        "status": "succeeded",
        "completed_at": completed,
        "last_error": None,
    })
    update_attempt(config, result["attempt_id"], {
        "status": "succeeded",
        "completed_at": completed,
        "exit_code": 0,
        "metadata_json": {
            "atomic_claim_certification": True,
            "race_workers": result["workers"],
            "winner_count": result["winner_count"],
            "null_claim_count": result["null_claim_count"],
        },
    })

    print("CCP11_ATOMIC_CLAIM_CERTIFICATION=PASS")
    print(f"JOB_ID={job['job_id']}")
    print(f"WORKERS={result['workers']}")
    print(f"WINNER_COUNT={result['winner_count']}")
    print(f"NULL_CLAIM_COUNT={result['null_claim_count']}")
    print(f"ATTEMPT_ID={result['attempt_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
