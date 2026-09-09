from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "research_outputs" / "runner"
STATE_FILE = STATE_DIR / "state.json"

JOBS = [
    {
        "id": "PMPD-POST9N-B1",
        "project": "pmpd",
        "module": "research_runner.jobs.pmpd_post9n_batch1",
        "description": "V5 contextual edge search: gap, time, geometry, RVOL, SPY/QQQ alignment",
    },
    {
        "id": "PMPD-EDGE-E1-B2",
        "project": "pmpd",
        "module": "research_runner.jobs.pmpd_edge_e1_batch2",
        "description": "Causal opening-RVOL availability audit and robustness decomposition of Batch-1 primary hypothesis",
    },
]


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {"version": 1, "jobs": {}}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def _save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def status() -> int:
    state = _load_state()
    print("=== TRADING RESEARCH RUNNER ===")
    print(f"ROOT={ROOT}")
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
        result = mod.run(ROOT)
        rec.update({"status": "PASS", "completed_at": datetime.now(timezone.utc).isoformat(), "result": result})
        _save_state(state)
        print(f">>> {job['id']} PASS")
        return 0
    except Exception as exc:
        rec.update({"status": "FAIL", "completed_at": datetime.now(timezone.utc).isoformat(), "error": repr(exc)})
        _save_state(state)
        print(f">>> {job['id']} FAIL: {exc}", file=sys.stderr)
        return 1


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
    p = argparse.ArgumentParser(description="Persistent TradingResearch local research runner")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    nxt = sub.add_parser("run-next")
    nxt.add_argument("--project", choices=["pmpd"])
    allp = sub.add_parser("run-all")
    allp.add_argument("--project", choices=["pmpd"])
    args = p.parse_args()
    if args.command == "status": return status()
    if args.command == "run-next": return run_next(args.project)
    if args.command == "run-all": return run_all(args.project)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
