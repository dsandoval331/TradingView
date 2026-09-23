from pathlib import Path
import pytest
from cloud_compute import research_revision_adapter as adapter


def test_targets_are_explicit_and_narrow():
    assert set(adapter.GOVERNED_RESEARCH_TARGETS) == {"PMOD-P2-B2", "IR11-P3-B2"}


def test_verify_commit_requires_full_sha(tmp_path):
    with pytest.raises(RuntimeError, match="full 40-character"):
        adapter.verify_commit(tmp_path, "abc123")


def test_unapproved_job_is_rejected(tmp_path):
    with pytest.raises(RuntimeError, match="not approved"):
        adapter.run_governed_revision(repo_root=tmp_path, work_root=tmp_path, runner_job_id="NOT-APPROVED", research_sha="1" * 40)


def test_materialize_module_verifies_exact_sha(monkeypatch, tmp_path):
    calls = []
    def fake_git(repo_root: Path, *args: str) -> str:
        calls.append(args)
        if args[0] == "rev-parse": return "1" * 40 + "\n"
        if args[0] == "show": return "def run(work_root):\n    return {'ok': True}\n"
        raise AssertionError(args)
    monkeypatch.setattr(adapter, "_git", fake_git)
    out = adapter.materialize_module(tmp_path, "1" * 40, "x.py", tmp_path / "out.py")
    assert out.read_text() == "def run(work_root):\n    return {'ok': True}\n"
    assert calls == [("rev-parse", "1" * 40 + "^{commit}"), ("show", "1" * 40 + ":x.py")]


def test_run_governed_revision_records_provenance(monkeypatch, tmp_path):
    sha = "2" * 40
    monkeypatch.setattr(adapter, "verify_commit", lambda repo_root, research_sha: sha)
    def fake_materialize(repo_root, research_sha, module_path, destination):
        destination.write_text("def run(work_root):\n    return {'artifact': 'a.csv'}\n", encoding="utf-8")
        return destination
    monkeypatch.setattr(adapter, "materialize_module", fake_materialize)
    result = adapter.run_governed_revision(repo_root=tmp_path, work_root=tmp_path, runner_job_id="PMOD-P2-B2", research_sha=sha)
    assert result["artifact"] == "a.csv"
    assert result["governed_research_sha"] == sha
    assert result["exact_research_sha_verified"] is True
