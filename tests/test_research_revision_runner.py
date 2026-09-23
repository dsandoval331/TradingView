from pathlib import Path

import pytest

from cloud_compute.research_revision import ResearchRevision
from cloud_compute.research_revision_runner import run_historical_job


def test_historical_runner_surfaces_child_failure(tmp_path):
    root = tmp_path / "research"
    root.mkdir()
    revision = ResearchRevision("1" * 40, "2" * 40, root)
    with pytest.raises(RuntimeError, match="historical research runner failed"):
        run_historical_job(
            revision,
            runner_job_id="MISSING",
            input_root=tmp_path / "inputs",
            output_dir=tmp_path / "outputs",
            parameters={},
        )
