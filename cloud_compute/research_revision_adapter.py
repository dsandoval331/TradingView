from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class GovernedResearchTarget:
    runner_job_id: str
    module_path: str
    callable_name: str = "run"
    execution_mode: str = "callable"


GOVERNED_RESEARCH_TARGETS: dict[str, GovernedResearchTarget] = {
    "SW10-S2-B5-ACQUISITION": GovernedResearchTarget("SW10-S2-B5-ACQUISITION", "tr_platform/research/swing10_s2_b5_acquisition.py", execution_mode="swing10_b5_acquisition_bundle"),
    "SW10-S2-B5-PREFLIGHT": GovernedResearchTarget("SW10-S2-B5-PREFLIGHT", "tr_platform/research/swing10_s2_b5_preflight.py", execution_mode="swing10_b5_preflight_bundle"),
    "SW10-S2-B4": GovernedResearchTarget("SW10-S2-B4", "tr_platform/research/swing10_s2_b4.py", execution_mode="swing10_b4_scientific_bundle"),
    "SW10-S2-B4-PREFLIGHT": GovernedResearchTarget("SW10-S2-B4-PREFLIGHT", "tr_platform/research/swing10_s2_b4_preflight.py", execution_mode="swing10_b4_preflight_bundle"),
    "SW10-S2-B3": GovernedResearchTarget("SW10-S2-B3", "tr_platform/research/swing10_s2_b3.py", execution_mode="swing10_b3_scientific_bundle"),
    "SW10-S2-B3-CONTINUOUS-PREFLIGHT": GovernedResearchTarget("SW10-S2-B3-CONTINUOUS-PREFLIGHT", "tr_platform/research/swing10_s2_b3_continuous_preflight.py", execution_mode="swing10_b3_continuous_bundle"),
    "SW10-S2-B3-PREFLIGHT": GovernedResearchTarget("SW10-S2-B3-PREFLIGHT", "tr_platform/research/swing10_s2_b3_preflight.py", execution_mode="swing10_b3_preflight_bundle"),
    "SW10-S2-B2": GovernedResearchTarget("SW10-S2-B2", "tr_platform/research/swing10_s2_b2.py", execution_mode="swing10_b2_bundle"),
    "PMOD-P2-B2": GovernedResearchTarget("PMOD-P2-B2", "research_runner/jobs/pmod_p2_b2_certification.py"),
    "IR11-P3-B2": GovernedResearchTarget("IR11-P3-B2", "research_runner/jobs/ir11_p3_normalization_b2.py"),
    "SW10-S2-B1": GovernedResearchTarget("SW10-S2-B1", "tr_platform/research/swing10_s2_b1.py", execution_mode="swing10_snapshot_cli"),
}


def _git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo_root), *args], check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:500]}")
    return proc.stdout


def verify_commit(repo_root: Path, research_sha: str) -> str:
    if len(research_sha) != 40:
        raise RuntimeError("governed research SHA must be a full 40-character commit SHA")
    resolved = _git(repo_root, "rev-parse", f"{research_sha}^{{commit}}").strip()
    if resolved != research_sha:
        raise RuntimeError(f"research SHA mismatch: requested={research_sha} resolved={resolved}")
    return resolved


def materialize_module(repo_root: Path, research_sha: str, module_path: str, destination: Path) -> Path:
    verify_commit(repo_root, research_sha)
    content = _git(repo_root, "show", f"{research_sha}:{module_path}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return destination


def _find_swing10_snapshot(work_root: Path) -> Path:
    candidates = [
        work_root / "job_inputs" / "swing10" / "market_daily_history.csv",
        work_root / "governed_inputs" / "swing10" / "market_daily_history.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise RuntimeError("governed SW10 market_daily_history.csv input was not materialized")


def _snapshot_to_sqlite(snapshot: Path, work_root: Path) -> Path:
    frame = pd.read_csv(snapshot)
    required = ["symbol", "trade_date", "open", "high", "low", "close", "volume"]
    if list(frame.columns) != required:
        raise RuntimeError(f"unexpected SW10 snapshot columns: {list(frame.columns)}")
    db_path = work_root / "governed_inputs" / "swing10" / "market_daily_history.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    with sqlite3.connect(db_path) as conn:
        frame.to_sql("market_daily_history", conn, index=False, if_exists="replace")
    return db_path


def _run_swing10_snapshot_cli(module_file: Path, work_root: Path) -> dict[str, Any]:
    snapshot = _find_swing10_snapshot(work_root)
    db_path = _snapshot_to_sqlite(snapshot, work_root)
    out_dir = work_root / "research_outputs" / "swing10" / "s2_b1"
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, str(module_file), "--db-url", f"sqlite:///{db_path.as_posix()}", "--out", str(out_dir)],
        check=False, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"SW10-S2-B1 governed CLI failed rc={proc.returncode}: {proc.stderr.strip()[:1000]}")
    artifact = out_dir / "factor_tail_summary.csv"
    if not artifact.exists():
        raise RuntimeError("SW10-S2-B1 completed without factor_tail_summary.csv")
    return {
        "status": "PASS",
        "artifact": str(artifact.relative_to(work_root)),
        "output_paths": [str(artifact.relative_to(work_root))],
        "input_provenance": {"local_relative_path": str(snapshot.relative_to(work_root))},
    }


def _run_b2_bundle(repo_root: Path, sha: str, destination: Path, work_root: Path, *, preflight: bool = False, continuous: bool = False, scientific: bool = False) -> dict:
    # Both research files are loaded from the requested revision, never mixed
    # with an infrastructure revision's helper implementation.
    for path in ("tr_platform/__init__.py", "tr_platform/research/__init__.py"):
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    bundle = ("tr_platform/research/swing10_s2_b3_preflight.py", "tr_platform/research/swing10_causal_inputs.py") if preflight else ("tr_platform/research/swing10_s2_b2.py", "tr_platform/research/swing10_s2_b2_core.py")
    if continuous:
        bundle = ("tr_platform/research/swing10_s2_b3_continuous_preflight.py", "tr_platform/research/swing10_s2_b3_preflight.py", "tr_platform/research/swing10_causal_inputs.py")
    if scientific:
        bundle = ("tr_platform/research/swing10_s2_b3.py", "tr_platform/research/swing10_s2_b3_continuous_preflight.py", "tr_platform/research/swing10_s2_b3_preflight.py", "tr_platform/research/swing10_causal_inputs.py")
    for path in bundle:
        materialize_module(repo_root, sha, path, destination / path)
    result_path = destination / "result.json"
    module = "swing10_s2_b3_preflight" if preflight else "swing10_s2_b2"
    if continuous:
        module = "swing10_s2_b3_continuous_preflight"
    if scientific:
        module = "swing10_s2_b3"
    code = f"from pathlib import Path; import json,sys; from tr_platform.research.{module} import run; Path(sys.argv[2]).write_text(json.dumps(run(Path(sys.argv[1]))))"
    proc = subprocess.run([sys.executable, "-c", code, str(work_root.resolve()), str(result_path)],
                          cwd=destination, env={**os.environ, "PYTHONPATH": str(destination)}, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"SW10-S2-B2 exact research bundle failed: {proc.stderr[-2000:]}")
    return json.loads(result_path.read_text())


def _run_b4_bundle(repo_root: Path, sha: str, destination: Path, work_root: Path, *, scientific: bool = False) -> dict:
    for path in ("tr_platform/__init__.py", "tr_platform/research/__init__.py"):
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    names = ("swing10_s2_b4_preflight.py", "swing10_causal_inputs.py")
    if scientific:
        names += ("swing10_s2_b4.py", "swing10_s2_b4_contract.py")
    for name in names:
        materialize_module(repo_root, sha, "tr_platform/research/" + name, destination / "tr_platform/research" / name)
    materialize_module(repo_root, sha, "research_protocols/swing10/SW10_S2_B4_PREFLIGHT_V1.persisted.json",
                       destination / "tr_platform/research/SW10_S2_B4_PREFLIGHT_V1.persisted.json")
    if scientific:
        for name in ("SW10_S2_B4_PROTOCOL_V1.persisted.json", "SW10_S2_B4_PROTOCOL_V1_SUPPLEMENT_1.persisted.json"):
            materialize_module(repo_root, sha, "research_protocols/swing10/" + name,
                               destination / "tr_platform/research" / name)
    result_path = destination / "result.json"
    module = "swing10_s2_b4" if scientific else "swing10_s2_b4_preflight"
    code = f"from pathlib import Path; import json,sys; from tr_platform.research.{module} import run; Path(sys.argv[2]).write_text(json.dumps(run(Path(sys.argv[1]))))"
    proc = subprocess.run([sys.executable, "-c", code, str(work_root.resolve()), str(result_path)],
                          cwd=destination, env={**os.environ, "PYTHONPATH": str(destination)}, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"SW10-S2-B4-PREFLIGHT exact outcome-blind bundle failed: {proc.stderr[-2000:]}")
    return json.loads(result_path.read_text())


def _run_b5_bundle(repo_root: Path, sha: str, destination: Path, work_root: Path, *, scientific: bool = False) -> dict:
    for path in ("tr_platform/__init__.py", "tr_platform/research/__init__.py"):
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    names = ("swing10_s2_b5_preflight.py",)
    for name in names:
        materialize_module(repo_root, sha, "tr_platform/research/" + name, destination / "tr_platform/research" / name)
    materialize_module(repo_root, sha, "research_protocols/swing10/SW10_S2_B5_PREFLIGHT_V1.persisted.json",
                       destination / "tr_platform/research/SW10_S2_B5_PREFLIGHT_V1.persisted.json")
    result_path = destination / "result.json"
    module = "swing10_s2_b5_preflight"
    code = f"from pathlib import Path; import json,sys; from tr_platform.research.{module} import run; Path(sys.argv[2]).write_text(json.dumps(run(Path(sys.argv[1]))))"
    proc = subprocess.run([sys.executable, "-c", code, str(work_root.resolve()), str(result_path)],
                          cwd=destination, env={**os.environ, "PYTHONPATH": str(destination)}, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"SW10-S2-B4-PREFLIGHT exact outcome-blind bundle failed: {proc.stderr[-2000:]}")
    return json.loads(result_path.read_text())


def _run_b5_acquisition_bundle(repo_root: Path, sha: str, destination: Path, work_root: Path, *, scientific: bool = False) -> dict:
    for path in ("tr_platform/__init__.py", "tr_platform/research/__init__.py"):
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    names = ("swing10_s2_b5_acquisition.py",)
    for name in names:
        materialize_module(repo_root, sha, "tr_platform/research/" + name, destination / "tr_platform/research" / name)
    materialize_module(repo_root, sha, "research_protocols/swing10/SW10_S2_B5A_ACQUISITION_AUTHORITY.json",
                       destination / "tr_platform/research/SW10_S2_B5A_ACQUISITION_AUTHORITY.json")
    result_path = destination / "result.json"
    module = "swing10_s2_b5_acquisition"
    code = f"from pathlib import Path; import json,sys; from tr_platform.research.{module} import run; Path(sys.argv[2]).write_text(json.dumps(run(Path(sys.argv[1]))))"
    proc = subprocess.run([sys.executable, "-c", code, str(work_root.resolve()), str(result_path)],
                          cwd=destination, env={**os.environ, "PYTHONPATH": str(destination)}, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"SW10-S2-B4-PREFLIGHT exact outcome-blind bundle failed: {proc.stderr[-2000:]}")
    return json.loads(result_path.read_text())


def run_governed_revision(*, repo_root: Path, work_root: Path, runner_job_id: str, research_sha: str) -> dict[str, Any]:
    target = GOVERNED_RESEARCH_TARGETS.get(runner_job_id)
    if target is None:
        raise RuntimeError(f"runner job is not approved for governed revision adapter: {runner_job_id}")
    verified_sha = verify_commit(repo_root, research_sha)
    with tempfile.TemporaryDirectory(prefix="governed-research-") as td:
        module_file = materialize_module(repo_root, verified_sha, target.module_path, Path(td) / Path(target.module_path).name)
        if target.execution_mode == "swing10_b5_acquisition_bundle":
            result = _run_b5_acquisition_bundle(repo_root, verified_sha, Path(td), Path(work_root))
        elif target.execution_mode == "swing10_b5_preflight_bundle":
            result = _run_b5_bundle(repo_root, verified_sha, Path(td), Path(work_root))
        elif target.execution_mode == "swing10_b4_scientific_bundle":
            result = _run_b4_bundle(repo_root, verified_sha, Path(td), Path(work_root), scientific=True)
        elif target.execution_mode == "swing10_b4_preflight_bundle":
            result = _run_b4_bundle(repo_root, verified_sha, Path(td), Path(work_root))
        elif target.execution_mode == "swing10_b3_scientific_bundle":
            result = _run_b2_bundle(repo_root, verified_sha, Path(td), Path(work_root), scientific=True)
        elif target.execution_mode == "swing10_b3_continuous_bundle":
            result = _run_b2_bundle(repo_root, verified_sha, Path(td), Path(work_root), continuous=True)
        elif target.execution_mode == "swing10_b3_preflight_bundle":
            result = _run_b2_bundle(repo_root, verified_sha, Path(td), Path(work_root), preflight=True)
        elif target.execution_mode == "swing10_b2_bundle":
            result = _run_b2_bundle(repo_root, verified_sha, Path(td), Path(work_root))
        elif target.execution_mode == "swing10_snapshot_cli":
            result = _run_swing10_snapshot_cli(module_file, Path(work_root))
        else:
            spec = importlib.util.spec_from_file_location(f"governed_{runner_job_id.lower().replace('-', '_')}", module_file)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"unable to load governed module: {target.module_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            fn = getattr(module, target.callable_name, None)
            if not callable(fn):
                raise RuntimeError(f"governed module has no callable {target.callable_name}: {target.module_path}")
            result = fn(Path(work_root))
    if not isinstance(result, dict):
        raise RuntimeError("governed research runner must return a dict")
    return {**result, "governed_research_sha": verified_sha, "governed_research_module": target.module_path, "exact_research_sha_verified": True}
