from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = Path(os.environ.get("TR_WORK_ROOT", str(CODE_ROOT))).expanduser().resolve()
STATE_DIR = WORK_ROOT / "research_outputs" / "runner"
STATE_FILE = STATE_DIR / "state.json"

JOBS = [
    {"id": "CCP3-PARITY-FIXTURE", "project": "ccp", "module": "research_runner.jobs.ccp3_parity_fixture", "description": "Deterministic native/container research_runner parity fixture"},
    {"id": "CCP4-REMOTE-FIXTURE", "project": "ccp4", "module": "research_runner.jobs.ccp4_remote_fixture", "description": "Representative remote-input cloud execution certification fixture"},
    {"id": "CCP8-RETRY-ONCE-FIXTURE", "project": "ccp", "module": "research_runner.jobs.ccp8_retry_once_fixture", "description": "Deterministic autonomous-loop fail-once then succeed retry fixture"},
    {"id": "CCP10-MARKET-DATA-INPUT", "project": "ccp", "module": "research_runner.jobs.ccp10_market_data_input_fixture", "description": "Checksum-verified Supabase Storage market-data materialization smoke fixture"},
    {"id": "CCP10-PMPD-EDGE-E1-B2-POC", "project": "ccp", "module": "research_runner.jobs.ccp10_pmpd_edge_e1_batch2_poc", "description": "CCP-10 proof wrapper around unchanged PMPD EDGE-E1 Batch-2 research logic"},
    {"id": "PMPD-POST9N-B1", "project": "pmpd", "module": "research_runner.jobs.pmpd_post9n_batch1", "description": "V5 contextual edge search: gap, time, geometry, RVOL, SPY/QQQ alignment"},
    {"id": "PMPD-EDGE-E1-B2", "project": "pmpd", "module": "research_runner.jobs.pmpd_edge_e1_batch2", "description": "Causal opening-RVOL availability audit and robustness decomposition of Batch-1 primary hypothesis"},
    {"id": "PMPD-EDGE-E1-B3", "project": "pmpd", "module": "research_runner.jobs.pmpd_edge_e1_batch3", "description": "RVOL incremental-edge, concentration, timing, direction, and prior-completed-bar audit"},
    {"id": "PMPD-EDGE-E1-B4", "project": "pmpd", "module": "research_runner.jobs.pmpd_edge_e1_batch4", "description": "Matched-control and incremental-information audit of frozen opening-RVOL hypothesis"},
    {"id": "PMPD-EDGE-E1-B5", "project": "pmpd", "module": "research_runner.jobs.pmpd_edge_e1_batch5", "description": "Breakout-volume anomaly and opening-momentum contextual edge research"},
    {"id": "PMPD-EDGE-E2-B1", "project": "pmpd", "module": "research_runner.jobs.pmpd_edge_e2_batch1", "description": "Outcome-blind penetration-versus-acceptance taxonomy and measurement protocol freeze"},
    {"id": "PMPD-EDGE-E2-B2", "project": "pmpd", "module": "research_runner.jobs.pmpd_edge_e2_batch2", "description": "Causal acceptance-state path construction and availability/coverage certification"},
    {"id": "PMPD-EDGE-E2-B2-AUDIT", "project": "pmpd", "module": "research_runner.jobs.pmpd_edge_e2_batch2_audit", "description": "Mechanical audit and concise extraction of persisted E2-B2 outputs"},
    {"id": "PMPD-EDGE-E2-B2-R2", "project": "pmpd", "module": "research_runner.jobs.pmpd_edge_e2_batch2_r2", "description": "Boundary-integrity rerun deriving frozen six-level stack from governed raw cache"},
    {"id": "PMPD-EDGE-E2-B3-R2", "project": "pmpd", "module": "research_runner.jobs.pmpd_edge_e2_batch3_r2", "description": "State-anchored +/-0.50% acceptance outcome comparison from certified E2-B2-R2 paths"},
    {"id": "PMPD-EDGE-E2-B3-AUDIT", "project": "pmpd", "module": "research_runner.jobs.pmpd_edge_e2_batch3_audit", "description": "Mechanical audit and concise extraction of E2-B3 state-anchored outcome evidence"},
]


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {"version": 1, "jobs": {}}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def _save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _git_sha() -> str | None:
    injected = os.environ.get("TR_GIT_SHA")
    if injected and injected != "unknown":
        return injected
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=CODE_ROOT, text=True).strip()
    except Exception:
        return injected or None


def _find_job(job_id: str) -> dict | None:
    return next((job for job in JOBS if job["id"] == job_id), None)


def status() -> int:
    state = _load_state()
    print("=== TRADING RESEARCH RUNNER ===")
    print(f"CODE_ROOT={CODE_ROOT}")
    print(f"WORK_ROOT={WORK_ROOT}")
    print(f"GIT_SHA={_git_sha()}")
    for job in JOBS:
        rec = state["jobs"].get(job["id"], {})
        print(f"{job['id']}: {rec.get('status', 'READY')} - {job['description']}")
    return 0


def run_job(job: dict) -> int:
    state = _load_state()
    rec = state["jobs"].setdefault(job["id"], {})
    rec.update({"status": "RUNNING", "started_at": datetime.now(timezone.utc).isoformat(), "git_sha": _git_sha()})
    _save_state(state)
    print(f"\n>>> RUNNING {job['id']}: {job['description']}")
    try:
        mod = importlib.import_module(job["module"])
        result = mod.run(WORK_ROOT)
        rec.update({"status": "PASS", "completed_at": datetime.now(timezone.utc).isoformat(), "result": result})
        _save_state(state)
        print(f">>> {job['id']} PASS")
        return 0
    except Exception as exc:
        rec.update({"status": "FAIL", "completed_at": datetime.now(timezone.utc).isoformat(), "error": repr(exc)})
        _save_state(state)
        print(f">>> {job['id']} FAIL: {exc}", file=sys.stderr)
        return 1


def run_id(job_id: str) -> int:
    job = _find_job(job_id)
    if job is None:
        print(f"UNKNOWN_JOB_ID={job_id}", file=sys.stderr)
        return 2
    return run_job(job)


def run_next(project: str | None = None) -> int:
    state = _load_state()
    candidates = [j for j in JOBS if project is None or j["project"] == project]
    for job in candidates:
        if state["jobs"].get(job["id"], {}).get("status") != "PASS":
            return run_job(job)
    print("NO_PENDING_JOBS")
    return 0


def run_all(project: str | None = None) -> int:
    state = _load_state()
    candidates = [j for j in JOBS if project is None or j["project"] == project]
    for job in candidates:
        if state["jobs"].get(job["id"], {}).get("status") == "PASS":
            continue
        rc = run_job(job)
        if rc:
            return rc
    print("ALL_PENDING_JOBS_COMPLETE")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Persistent TradingResearch local/cloud-compatible research runner")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    one = sub.add_parser("run-id")
    one.add_argument("job_id")
    nxt = sub.add_parser("run-next")
    nxt.add_argument("--project", choices=["ccp", "ccp4", "pmpd"])
    allp = sub.add_parser("run-all")
    allp.add_argument("--project", choices=["ccp", "ccp4", "pmpd"])
    args = p.parse_args()
    if args.command == "status": return status()
    if args.command == "run-id": return run_id(args.job_id)
    if args.command == "run-next": return run_next(args.project)
    if args.command == "run-all": return run_all(args.project)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
