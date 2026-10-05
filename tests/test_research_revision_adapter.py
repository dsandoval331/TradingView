from pathlib import Path
import pytest
from cloud_compute import research_revision_adapter as adapter


def test_targets_are_explicit_and_narrow():
    assert set(adapter.GOVERNED_RESEARCH_TARGETS) == {"SW11-S3P", "SW11-S2B", "SW11-S2A-CERT", "SW11-S2A", "SW10-S3", "SW10-S3-ARTIFACT-CERT", "SW10-S3-PREFLIGHT", "PMOD-P2-B2", "IR11-P3-B2", "SW10-S2-B1", "SW10-S2-B2", "SW10-S2-B3-PREFLIGHT", "SW10-S2-B3-CONTINUOUS-PREFLIGHT", "SW10-S2-B3", "SW10-S2-B4-PREFLIGHT", "SW10-S2-B4", "SW10-S2-B5-PREFLIGHT", "SW10-S2-B5-ACQUISITION", "SW10-S2-B5"}
    target = adapter.GOVERNED_RESEARCH_TARGETS["SW10-S2-B1"]
    assert target.module_path == "tr_platform/research/swing10_s2_b1.py"
    assert target.execution_mode == "swing10_snapshot_cli"


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


def test_swing10_snapshot_must_be_materialized(tmp_path):
    with pytest.raises(RuntimeError, match="was not materialized"):
        adapter._find_swing10_snapshot(tmp_path)


def test_swing10_snapshot_contract(monkeypatch, tmp_path):
    snapshot = tmp_path / "job_inputs" / "swing10" / "market_daily_history.csv"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("symbol,trade_date,open,high,low,close,volume\nAAPL,2026-01-02,1,2,0.5,1.5,100\n", encoding="utf-8")
    module = tmp_path / "swing10.py"
    module.write_text("# fixture\n", encoding="utf-8")
    calls = []
    class Proc:
        returncode = 0
        stderr = ""
        stdout = ""
    def fake_run(args, **kwargs):
        calls.append(args)
        out = Path(args[args.index("--out") + 1])
        out.mkdir(parents=True, exist_ok=True)
        (out / "factor_tail_summary.csv").write_text("factor,side_tail\n", encoding="utf-8")
        return Proc()
    monkeypatch.setattr(adapter.subprocess, "run", fake_run)
    result = adapter._run_swing10_snapshot_cli(module, tmp_path)
    assert "--db-url" in calls[0]
    assert calls[0][calls[0].index("--db-url") + 1].startswith("sqlite:///")
    assert result["status"] == "PASS"
    assert result["artifact"].endswith("factor_tail_summary.csv")
    assert result["input_provenance"]["local_relative_path"].endswith("market_daily_history.csv")
