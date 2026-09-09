from pathlib import Path

from cloud_compute.container_contract import inspect_contract


def test_contract_reports_separate_workspace(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "code"
    (root / "research_runner").mkdir(parents=True)
    (root / "requirements.txt").write_text("pandas\n", encoding="utf-8")
    (root / "research_runner" / "runner.py").write_text("# runner\n", encoding="utf-8")
    work = tmp_path / "work"
    monkeypatch.setenv("TR_WORK_ROOT", str(work))
    monkeypatch.setenv("TR_GIT_SHA", "abc123")
    record = inspect_contract(root)
    assert record["workspace_separated"] is True
    assert record["git_sha"] == "abc123"
    assert record["requirements_present"] is True
    assert record["runner_present"] is True
