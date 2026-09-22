from __future__ import annotations
import argparse, importlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
CODE_ROOT=Path(__file__).resolve().parents[1]
WORK_ROOT=Path(os.environ.get("TR_WORK_ROOT",str(CODE_ROOT))).expanduser().resolve()
STATE_DIR=WORK_ROOT/"research_outputs"/"runner"; STATE_FILE=STATE_DIR/"state.json"
JOBS=[
{"id":"PMPD-POST9N-B1","project":"pmpd","module":"research_runner.jobs.pmpd_post9n_batch1","description":"V5 contextual edge search: gap, time, geometry, RVOL, SPY/QQQ alignment"},
{"id":"PMPD-EDGE-E1-B2","project":"pmpd","module":"research_runner.jobs.pmpd_edge_e1_batch2","description":"Causal opening-RVOL availability audit and robustness decomposition of Batch-1 primary hypothesis"},
{"id":"PMPD-EDGE-E1-B3","project":"pmpd","module":"research_runner.jobs.pmpd_edge_e1_batch3","description":"RVOL incremental-edge, concentration, timing, direction, and prior-completed-bar audit"},
{"id":"PMPD-EDGE-E1-B4","project":"pmpd","module":"research_runner.jobs.pmpd_edge_e1_batch4","description":"Matched-control and incremental-information audit of frozen opening-RVOL hypothesis"},
{"id":"PMPD-EDGE-E1-B5","project":"pmpd","module":"research_runner.jobs.pmpd_edge_e1_batch5","description":"Breakout-volume anomaly and opening-momentum contextual edge research"},
{"id":"PMOD-P2-B2","project":"pmod","module":"research_runner.jobs.pmod_p2_b2_certification","description":"PMOD P2 Batch 2 governed partition and snapshot certification"},
]
def _load_state():
    if not STATE_FILE.exists(): return {"version":1,"jobs":{}}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))
def _save_state(state):
    STATE_DIR.mkdir(parents=True,exist_ok=True); STATE_FILE.write_text(json.dumps(state,indent=2),encoding="utf-8")
def _git_sha():
    injected=os.environ.get("TR_GIT_SHA")
    if injected and injected!="unknown": return injected
    try:return subprocess.check_output(["git","rev-parse","HEAD"],cwd=CODE_ROOT,text=True).strip()
    except Exception:return injected or None
def _find_job(job_id): return next((j for j in JOBS if j["id"]==job_id),None)
def status():
    state=_load_state(); print("=== TRADING RESEARCH RUNNER ==="); print(f"CODE_ROOT={CODE_ROOT}"); print(f"WORK_ROOT={WORK_ROOT}"); print(f"GIT_SHA={_git_sha()}")
    for job in JOBS: print(f"{job['id']}: {state['jobs'].get(job['id'],{}).get('status','READY')} - {job['description']}")
    return 0
def run_job(job):
    state=_load_state(); rec=state["jobs"].setdefault(job["id"],{}); rec.update({"status":"RUNNING","started_at":datetime.now(timezone.utc).isoformat(),"git_sha":_git_sha()}); _save_state(state); print(f"\n>>> RUNNING {job['id']}: {job['description']}")
    try:
        result=importlib.import_module(job["module"]).run(WORK_ROOT); rec.update({"status":"PASS","completed_at":datetime.now(timezone.utc).isoformat(),"result":result}); _save_state(state); print(f">>> {job['id']} PASS"); return 0
    except Exception as exc:
        rec.update({"status":"FAIL","completed_at":datetime.now(timezone.utc).isoformat(),"error":repr(exc)}); _save_state(state); print(f">>> {job['id']} FAIL: {exc}",file=sys.stderr); return 1
def run_id(job_id):
    job=_find_job(job_id)
    if job is None: print(f"UNKNOWN_JOB_ID={job_id}",file=sys.stderr); return 2
    return run_job(job)
def run_next(project=None):
    state=_load_state(); candidates=[j for j in JOBS if project is None or j["project"]==project]
    for job in candidates:
        if state["jobs"].get(job["id"],{}).get("status")!="PASS": return run_job(job)
    print("NO_PENDING_JOBS"); return 0
def run_all(project=None):
    state=_load_state(); candidates=[j for j in JOBS if project is None or j["project"]==project]
    for job in candidates:
        if state["jobs"].get(job["id"],{}).get("status")=="PASS": continue
        rc=run_job(job)
        if rc:return rc
    print("ALL_PENDING_JOBS_COMPLETE"); return 0
def main():
    p=argparse.ArgumentParser(description="Persistent TradingResearch local/cloud-compatible research runner"); sub=p.add_subparsers(dest="command",required=True); sub.add_parser("status"); one=sub.add_parser("run-id"); one.add_argument("job_id"); nxt=sub.add_parser("run-next"); nxt.add_argument("--project",choices=["pmpd","pmod"]); allp=sub.add_parser("run-all"); allp.add_argument("--project",choices=["pmpd","pmod"]); args=p.parse_args()
    if args.command=="status":return status()
    if args.command=="run-id":return run_id(args.job_id)
    if args.command=="run-next":return run_next(args.project)
    if args.command=="run-all":return run_all(args.project)
    return 2
if __name__=="__main__":raise SystemExit(main())
