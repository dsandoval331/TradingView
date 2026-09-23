from pathlib import Path

from cloud_compute import governed_execution
from cloud_compute.research_revision import ResearchRevision


def test_governed_execution_preserves_dual_sha(monkeypatch, tmp_path):
    revision = ResearchRevision("1" * 40, "2" * 40, tmp_path / "revision")
    monkeypatch.setattr(governed_execution, "materialize_research_revision", lambda **kwargs: revision)
    monkeypatch.setattr(governed_execution, "remove_research_revision", lambda **kwargs: None)
    monkeypatch.setattr(governed_execution, "run_historical_job", lambda *args, **kwargs: {"artifacts": []})
    result, meta = governed_execution.execute_governed_research(
        repository_root=tmp_path,
        research_sha="1" * 40,
        runner_job_id="TEST",
        input_root=tmp_path / "inputs",
        output_dir=tmp_path / "outputs",
        parameters={},
    )
    assert result == {"artifacts": []}
    assert meta["research_sha"] == "1" * 40
    assert meta["infrastructure_sha"] == "2" * 40
    assert meta["exact_research_sha_verified"] is True
