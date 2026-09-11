from __future__ import annotations

import os
import subprocess

from cloud_compute.control_plane import ControlPlaneConfig, create_job

STRATEGY_ID = "84fb30c1-7600-49bf-a024-022f0500492e"
RUNNER_JOB_ID = "PMPD-EDGE-E2-B1"
PROJECT_CODE = "PMPD"
PHASE_CODE = "E2"
DATASET_VERSION = "PMPD-EDGE-E2-B1-PROTOCOL-V1"


def _git_sha() -> str:
    injected = os.environ.get("TR_GIT_SHA")
    if injected:
        return injected.strip()
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def main() -> int:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")

    git_sha = _git_sha()
    config = ControlPlaneConfig(url, key)
    job = create_job(config, {
        "strategy_id": STRATEGY_ID,
        "research_run_id": None,
        "runner_job_id": RUNNER_JOB_ID,
        "project_code": PROJECT_CODE,
        "phase_code": PHASE_CODE,
        "status": "queued",
        "preferred_executor": "github_actions",
        "assigned_executor": None,
        "cloud_run_spend_approved": False,
        "priority": 100,
        "git_sha": git_sha,
        "container_image": None,
        "dataset_version": DATASET_VERSION,
        "parameters_json": {
            "purpose": "Outcome-blind penetration-versus-acceptance taxonomy and measurement protocol freeze",
            "protocol": "PMPD_EDGE_E2_ACCEPTANCE_PROTOCOL_V1",
            "submission_source": "pmpd_edge_e2_b1_governed_submitter",
            "attempt_count": 0,
            "research_only": True,
            "2026_is_development_evidence": True,
            "v4_modified": False,
            "v5_modified": False,
            "production_rule_authorized": False,
            "outcome_comparison_performed": False,
            "cost_policy": "ZERO_INCREMENTAL_COST_FIRST",
        },
    })
    job_id = str(job["job_id"])
    print("PMPD_EDGE_E2_B1_CONTROL_PLANE_SUBMISSION=PASS")
    print(f"JOB_ID={job_id}")
    print(f"RUNNER_JOB_ID={RUNNER_JOB_ID}")
    print(f"GIT_SHA={git_sha}")
    print("INPUTS=0")
    print("PREFERRED_EXECUTOR=github_actions")
    print("CLOUD_RUN_SPEND_APPROVED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
