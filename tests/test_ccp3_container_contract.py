from pathlib import Path

from research_runner import runner


def test_research_dockerfile_preserves_runner_contract() -> None:
    text = Path("Dockerfile.research").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in text
    assert "TR_WORK_ROOT=/workspace" in text
    assert "TR_GIT_SHA=${TR_GIT_SHA}" in text
    assert 'ENTRYPOINT ["python", "-m", "research_runner.runner"]' in text
    assert 'CMD ["status"]' in text


def test_dockerignore_excludes_runtime_data_and_secrets() -> None:
    text = Path(".dockerignore").read_text(encoding="utf-8").splitlines()
    required = {".git", ".venv", ".env", ".env.*", "market_cache", "research_outputs", "*.parquet"}
    assert required.issubset(set(text))


def test_git_sha_can_be_injected_without_git_metadata(monkeypatch) -> None:
    monkeypatch.setenv("TR_GIT_SHA", "abc123")
    assert runner._git_sha() == "abc123"
