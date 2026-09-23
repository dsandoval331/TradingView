from __future__ import annotations

import importlib.util
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GovernedResearchTarget:
    runner_job_id: str
    module_path: str
    callable_name: str = "run"


# Explicit allow-list: historical execution is never inferred from arbitrary job input.
GOVERNED_RESEARCH_TARGETS: dict[str, GovernedResearchTarget] = {
    "PMOD-P2-B2": GovernedResearchTarget("PMOD-P2-B2", "research_runner/jobs/pmod_p2_b2_certification.py"),
    "IR11-P3-B2": GovernedResearchTarget("IR11-P3-B2", "research_runner/jobs/ir11_p3_normalization_b2.py"),
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


def run_governed_revision(*, repo_root: Path, work_root: Path, runner_job_id: str, research_sha: str) -> dict[str, Any]:
    target = GOVERNED_RESEARCH_TARGETS.get(runner_job_id)
    if target is None:
        raise RuntimeError(f"runner job is not approved for governed revision adapter: {runner_job_id}")
    verified_sha = verify_commit(repo_root, research_sha)
    with tempfile.TemporaryDirectory(prefix="governed-research-") as td:
        module_file = materialize_module(repo_root, verified_sha, target.module_path, Path(td) / Path(target.module_path).name)
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
