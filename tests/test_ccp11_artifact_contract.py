from pathlib import Path

import pytest

from cloud_compute.artifact_contract import completeness_summary, declared_output_paths, validate_declared_outputs


def test_declared_output_paths_include_primary_and_named_secondaries() -> None:
    result = {
        "output_dir": "research_outputs/demo",
        "artifact": "research_outputs/demo/summary.json",
        "summary": "research_outputs/demo/summary.json",
        "table": "research_outputs/demo/table.csv",
        "sha256": "not-a-path",
        "flag": True,
    }
    assert declared_output_paths(result) == [
        "research_outputs/demo/summary.json",
        "research_outputs/demo/table.csv",
    ]


def test_validate_and_summarize_multiple_outputs(tmp_path: Path) -> None:
    out = tmp_path / "research_outputs" / "demo"
    out.mkdir(parents=True)
    (out / "summary.json").write_text("{}", encoding="utf-8")
    (out / "table.csv").write_text("a\n1\n", encoding="utf-8")
    result = {
        "artifact": "research_outputs/demo/summary.json",
        "summary": "research_outputs/demo/summary.json",
        "table": "research_outputs/demo/table.csv",
    }
    paths = validate_declared_outputs(result, work_root=tmp_path)
    assert len(paths) == 2
    summary = completeness_summary(result, work_root=tmp_path)
    assert summary["declared_file_count"] == 2
    assert summary["primary_in_declared_files"] is True


def test_missing_declared_output_fails_closed(tmp_path: Path) -> None:
    result = {"artifact": "research_outputs/demo/missing.json"}
    with pytest.raises(RuntimeError, match="declared artifact does not exist"):
        validate_declared_outputs(result, work_root=tmp_path)


def test_path_escape_fails_closed(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    result = {"artifact": "../outside.txt"}
    with pytest.raises(RuntimeError, match="escapes work root"):
        validate_declared_outputs(result, work_root=tmp_path)
