from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from cloud_compute.research_revision import materialize_research_revision, provenance, remove_research_revision
from cloud_compute.research_revision_runner import run_historical_job


def execute_governed_research(
    *,
    repository_root: Path,
    research_sha: str,
    runner_job_id: str,
    input_root: Path,
    output_dir: Path,
    parameters: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, object]]:
    """Run exact historical research code under the current certified infrastructure checkout."""
    with tempfile.TemporaryDirectory(prefix="governed-research-") as temp:
        destination = Path(temp) / "revision"
        revision = materialize_research_revision(
            repository_root=repository_root,
            research_sha=research_sha,
            destination=destination,
        )
        try:
            result = run_historical_job(
                revision,
                runner_job_id=runner_job_id,
                input_root=input_root,
                output_dir=output_dir,
                parameters=parameters,
            )
            return result, provenance(revision)
        finally:
            remove_research_revision(repository_root=repository_root, revision=revision)
