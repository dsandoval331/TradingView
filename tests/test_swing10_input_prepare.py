import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cloud_compute import swing10_input_prepare as prep
from cloud_compute.artifact_contract import declared_output_paths, primary_output_path
from cloud_compute import research_revision_adapter as adapter


def test_prepare_rejects_other_jobs():
    with pytest.raises(RuntimeError, match="restricted"):
        prep.prepare(None, "unrelated-job")


def test_panel_rejects_wrong_coverage_and_duplicates():
    f = pd.DataFrame([["A", "2025-02-03", 1, 2, .5, 1, 10]], columns=prep.COLUMNS)
    with pytest.raises(RuntimeError, match="coverage"):
        prep.validate_panel(f)
    with pytest.raises(RuntimeError, match="duplicate"):
        prep.validate_panel(pd.concat([f, f]))


def test_unstable_source_is_never_uploaded(monkeypatch):
    monkeypatch.setattr(prep, "_fetch_rows", lambda *a, **k: [{"git_sha": prep.RESEARCH_SHA, "dataset_version": prep.DATASET, "runner_job_id": "SW10-S2-B1"}])
    monkeypatch.setattr(prep, "fetch_job_inputs", lambda *a: [])
    exports = iter([(b"first", {}), (b"changed", {})])
    monkeypatch.setattr(prep, "export_panel", lambda *a: next(exports))
    monkeypatch.setattr(prep, "_upload_object", lambda *a, **k: pytest.fail("upload before stable certification"))
    with pytest.raises(RuntimeError, match="changed during export"):
        prep.prepare(None, prep.JOB_ID)


def test_frozen_cli_executes_on_materialized_snapshot(tmp_path):
    """Execute exact frozen source on synthetic prices, not research outcomes."""
    root = Path(__file__).resolve().parents[1]
    snapshot = tmp_path / prep.LOCAL_PATH
    snapshot.parent.mkdir(parents=True)
    dates = pd.bdate_range("2025-01-02", periods=300)
    rows = []
    for symbol, phase in [("FIXTURE_A", 0), ("FIXTURE_B", .5)]:
        for i, date in enumerate(dates):
            close = 100 + i / 10 + 2 * np.sin(i / 3 + phase)
            rows.append([symbol, date.strftime("%Y-%m-%d"), close * .999, close * 1.01, close * .99, close, 1000 + i])
    pd.DataFrame(rows, columns=prep.COLUMNS).to_csv(snapshot, index=False)
    before = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    result = adapter.run_governed_revision(repo_root=root, work_root=tmp_path, runner_job_id="SW10-S2-B1", research_sha=prep.RESEARCH_SHA)
    assert result["governed_research_sha"] == prep.RESEARCH_SHA
    assert result["exact_research_sha_verified"]
    assert declared_output_paths(result) == [result["artifact"]]
    assert primary_output_path(result) == result["artifact"]
    output = pd.read_csv(tmp_path / result["artifact"])
    assert len(output) == 144
    assert set(output.horizon_days) == {1, 2, 3, 5, 7, 10}
    assert set(output.factor) == {"RET_MOM", "SHORT_REV", "VOL_TURN", "HIGH52", "VOL_REGIME", "GAP_OVN"}
    # Snapshot bytes are not modified by the compatibility adapter.
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == before
