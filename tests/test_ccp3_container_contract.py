from pathlib import Path
from research_runner import runner

def test_research_dockerfile_preserves_runner_contract():
    text = Path('Dockerfile.research').read_text(encoding='utf-8')
    assert 'FROM python:3.12-slim' in text
    assert 'ARG TR_GIT_SHA' in text
    assert 'TR_WORK_ROOT=/workspace' in text
    assert 'TR_GIT_SHA=${TR_GIT_SHA}' in text
    assert 'python -m cloud_compute.container_contract' in text
    assert 'ENTRYPOINT ["python", "-m", "research_runner.runner"]' in text
    assert 'CMD ["status"]' in text

def test_dockerignore_excludes_runtime_data_and_secrets():
    lines = Path('.dockerignore').read_text(encoding='utf-8').splitlines()
    assert {'market_cache', 'research_outputs', '*.parquet', '.env'}.issubset(set(lines))

def test_git_sha_can_be_injected_without_git_metadata(monkeypatch):
    monkeypatch.setenv('TR_GIT_SHA', 'abc123')
    assert runner._git_sha() == 'abc123'
