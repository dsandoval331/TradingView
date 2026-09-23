from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from cloud_compute.research_revision import ResearchRevision


def run_historical_job(
    revision: ResearchRevision,
    *,
    runner_job_id: str,
    input_root: Path,
    output_dir: Path,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Execute runner.run_id from the verified research tree in a child Python process."""
    output_dir.mkdir(parents=True, exist_ok=True)
    script = (
        "import json,sys; "
        "from pathlib import Path; "
        "from research_runner import runner; "
        "job_id=sys.argv[1]; input_root=Path(sys.argv[2]); output_dir=Path(sys.argv[3]); "
        "params=json.loads(sys.argv[4]); "
        "print(json.dumps(runner.run_id(job_id,input_root=input_root,output_dir=output_dir,parameters=params),default=str))"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(revision.root) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-c", script, runner_job_id, str(input_root), str(output_dir), json.dumps(parameters)],
        cwd=revision.root,
        env=env,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"historical research runner failed ({proc.returncode}): {proc.stderr[-2000:]}")
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("historical research runner produced no JSON result")
    result = json.loads(lines[-1])
    if not isinstance(result, dict):
        raise RuntimeError("historical research runner result must be a JSON object")
    return result
