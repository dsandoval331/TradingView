from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from cloud_compute.control_plane import (
    ControlPlaneConfig,
    create_job,
    create_job_input,
    update_job,
)

STRATEGY_ID = "84fb30c1-7600-49bf-a024-022f0500492e"
RUNNER_JOB_ID = "PMPD-EDGE-E1-B5"
PROJECT_CODE = "PMPD"
PHASE_CODE = "E1"
DATASET_VERSION = "PMPD-EDGE-E1-B5-2026-DEV-V1"
BUCKET = "trading-research-market-data"
CONTEXT_ARTIFACT_ID = "81254126-7f71-4940-8a00-c67633415908"
CONTEXT_OBJECT_PATH = "upstream/pmpd/post9n_batch1/context_enriched.parquet"
CONTEXT_LOCAL_PATH = "research_outputs/pmpd/post9n_batch1/context_enriched.parquet"
CONTEXT_SIZE = 3865352
CONTEXT_SHA256 = "de184977c9b66035975f2faac4cfadfd95173875504c78c79ce454b30191affe"
PROMOTION_MANIFEST = Path("research_outputs/cloud_compute/pmpd_edge_e1_b5_2026_cache_promotion.json")
EXPECTED_SYMBOLS = 112


def _git_sha() -> str:
    injected = os.environ.get("TR_GIT_SHA")
    if injected:
        return injected.strip()
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _load_manifest(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"promotion manifest not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("manifest_version") != 1:
        raise RuntimeError("unexpected promotion manifest version")
    if payload.get("required_symbol_count") != EXPECTED_SYMBOLS:
        raise RuntimeError(f"expected {EXPECTED_SYMBOLS} required symbols")
    if payload.get("promoted_symbol_count") != EXPECTED_SYMBOLS:
        raise RuntimeError(f"expected {EXPECTED_SYMBOLS} promoted symbols")
    if payload.get("all_parity_pass") is not True:
        raise RuntimeError("promotion manifest parity is not PASS")
    entries = list(payload.get("entries") or [])
    if len(entries) != EXPECTED_SYMBOLS:
        raise RuntimeError(f"expected {EXPECTED_SYMBOLS} manifest entries, found {len(entries)}")

    seen: set[str] = set()
    for row in entries:
        symbol = str(row.get("symbol") or "").upper().strip()
        if not symbol or symbol in seen:
            raise RuntimeError(f"invalid or duplicate symbol in manifest: {symbol!r}")
        seen.add(symbol)
        expected_object = f"upstream/pmpd/market_cache/1m/{symbol}/2026.parquet"
        expected_local = f"data/second1m_alt_entry_cache_v1/partitions/{symbol}/{symbol}_2026.parquet"
        if row.get("object_path") != expected_object:
            raise RuntimeError(f"unexpected object_path for {symbol}: {row.get('object_path')}")
        if row.get("local_relative_path") != expected_local:
            raise RuntimeError(f"unexpected local_relative_path for {symbol}: {row.get('local_relative_path')}")
        if row.get("bucket_name") != BUCKET:
            raise RuntimeError(f"unexpected bucket for {symbol}")
        if row.get("parity") is not True:
            raise RuntimeError(f"parity is not PASS for {symbol}")
        size = int(row.get("size_bytes") or 0)
        sha = str(row.get("sha256") or "").lower().strip()
        if size <= 0 or len(sha) != 64:
            raise RuntimeError(f"missing integrity metadata for {symbol}")
    return sorted(entries, key=lambda r: str(r["symbol"]))


def main() -> int:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")

    git_sha = _git_sha()
    entries = _load_manifest(PROMOTION_MANIFEST)
    config = ControlPlaneConfig(url, key)

    # Start blocked so no executor can claim a partially declared dependency set.
    job = create_job(config, {
        "strategy_id": STRATEGY_ID,
        "research_run_id": None,
        "runner_job_id": RUNNER_JOB_ID,
        "project_code": PROJECT_CODE,
        "phase_code": PHASE_CODE,
        "status": "blocked",
        "preferred_executor": "github_actions",
        "assigned_executor": None,
        "cloud_run_spend_approved": False,
        "priority": 100,
        "git_sha": git_sha,
        "container_image": None,
        "dataset_version": DATASET_VERSION,
        "parameters_json": {
            "purpose": "PMPD-EDGE E1 Batch 5 breakout-volume anomaly and opening-momentum contextual research",
            "submission_source": "pmpd_edge_e1_b5_governed_submitter",
            "attempt_count": 0,
            "research_only": True,
            "2026_is_development_evidence": True,
            "v4_modified": False,
            "v5_modified": False,
            "rvol_threshold_retuned": False,
            "production_rule_authorized": False,
            "frozen_rvol_threshold": 1.5,
            "bootstrap_reps": 10000,
            "bootstrap_seed": 9142026,
            "cost_policy": "ZERO_INCREMENTAL_COST_FIRST",
        },
    })
    job_id = str(job["job_id"])

    try:
        create_job_input(config, {
            "job_id": job_id,
            "input_type": "upstream_artifact",
            "dataset_version": DATASET_VERSION,
            "object_path": CONTEXT_OBJECT_PATH,
            "object_size_bytes": CONTEXT_SIZE,
            "sha256": CONTEXT_SHA256,
            "required": True,
            "metadata_json": {
                "bucket_name": BUCKET,
                "local_relative_path": CONTEXT_LOCAL_PATH,
                "dependency_manifest_v1": True,
                "source_artifact_id": CONTEXT_ARTIFACT_ID,
            },
        })

        for row in entries:
            create_job_input(config, {
                "job_id": job_id,
                "input_type": "market_data",
                "dataset_version": DATASET_VERSION,
                "object_path": row["object_path"],
                "object_size_bytes": int(row["size_bytes"]),
                "sha256": str(row["sha256"]).lower(),
                "required": True,
                "metadata_json": {
                    "bucket_name": BUCKET,
                    "local_relative_path": row["local_relative_path"],
                    "dependency_manifest_v1": True,
                    "symbol": row["symbol"],
                    "year": 2026,
                },
            })

        update_job(config, job_id, {
            "status": "queued",
            "last_error": None,
        })
    except Exception as exc:
        update_job(config, job_id, {
            "status": "blocked",
            "last_error": f"dependency registration failed: {exc}",
        })
        raise

    print("PMPD_EDGE_E1_B5_CONTROL_PLANE_SUBMISSION=PASS")
    print(f"JOB_ID={job_id}")
    print(f"RUNNER_JOB_ID={RUNNER_JOB_ID}")
    print(f"GIT_SHA={git_sha}")
    print(f"INPUTS={1 + len(entries)}")
    print("PREFERRED_EXECUTOR=github_actions")
    print("CLOUD_RUN_SPEND_APPROVED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
