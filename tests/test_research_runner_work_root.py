from __future__ import annotations

import importlib
from pathlib import Path


def test_runner_work_root_defaults_to_code_root(monkeypatch) -> None:
    monkeypatch.delenv("TR_WORK_ROOT", raising=False)
    import research_runner.runner as runner

    runner = importlib.reload(runner)
    assert runner.WORK_ROOT == runner.CODE_ROOT
    assert runner.STATE_FILE == runner.CODE_ROOT / "research_outputs" / "runner" / "state.json"


def test_runner_work_root_can_be_overridden(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TR_WORK_ROOT", str(tmp_path))
    import research_runner.runner as runner

    runner = importlib.reload(runner)
    assert runner.WORK_ROOT == tmp_path.resolve()
    assert runner.STATE_FILE == tmp_path.resolve() / "research_outputs" / "runner" / "state.json"

    monkeypatch.delenv("TR_WORK_ROOT", raising=False)
    importlib.reload(runner)
