from pathlib import Path


def test_research_dockerfile_preserves_runner_contract() -> None:
    text = Path("Dockerfile.research").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in text
    assert "TR_WORK_ROOT=/workspace" in text
    assert 'ENTRYPOINT ["python", "-m", "research_runner.runner"]' in text
    assert 'CMD ["status"]' in text


def test_dockerignore_excludes_runtime_data_and_secrets() -> None:
    text = Path(".dockerignore").read_text(encoding="utf-8").splitlines()
    required = {".git", ".venv", ".env", ".env.*", "market_cache", "research_outputs", "*.parquet"}
    assert required.issubset(set(text))
