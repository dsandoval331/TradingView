from pathlib import Path

from cloud_compute.executor_policy import Executor, ExecutorAvailability, choose_executor

DOC = Path('docs/cloud_compute/ccp12_operating_model.md')
QUICKSTART = Path('docs/cloud_compute/operator_quickstart.md')


def test_operating_model_document_exists_and_declares_version() -> None:
    text = DOC.read_text(encoding='utf-8')
    assert 'Operating model version: CCP12-1.0' in text
    assert 'NO_INCREMENTAL_SPEND_WITHOUT_EXPLICIT_APPROVAL' in text
    assert 'ZERO_INCREMENTAL_COST_FIRST' in text


def test_documented_executor_order_matches_runtime_policy() -> None:
    assert choose_executor(ExecutorAvailability()) == Executor.GITHUB_ACTIONS
    assert choose_executor(ExecutorAvailability(
        github_actions_available=False,
        cloud_run_available=True,
        cloud_run_spend_approved=False,
        local_windows_available=True,
    )) == Executor.LOCAL_WINDOWS
    assert choose_executor(ExecutorAvailability(
        github_actions_available=False,
        cloud_run_available=True,
        cloud_run_spend_approved=True,
        local_windows_available=True,
    )) == Executor.CLOUD_RUN


def test_operating_model_preserves_research_governance_boundary() -> None:
    text = DOC.read_text(encoding='utf-8')
    required = [
        'Research interpretation remains in the owning research thread/project',
        'must not independently change',
        'frozen model thresholds',
        'evidence classifications',
        'production authorization',
    ]
    for phrase in required:
        assert phrase in text


def test_operating_model_defines_reliability_and_artifact_controls() -> None:
    text = DOC.read_text(encoding='utf-8')
    for phrase in [
        'Atomic claims',
        'Stale jobs',
        'persist all declared output files',
        'SHA-256',
        'executor liveness is unknown: leave the job alone',
    ]:
        assert phrase in text


def test_operator_quickstart_documents_cloud_first_and_local_fallback() -> None:
    text = QUICKSTART.read_text(encoding='utf-8')
    for phrase in [
        'Routine operation should not require a local `git pull` or manual PowerShell execution loop.',
        'python -m cloud_compute.local_worker --job-id <JOB_ID>',
        'GitHub Actions -> Local Windows',
        'NO_INCREMENTAL_SPEND_WITHOUT_EXPLICIT_APPROVAL',
        'Infrastructure can execute research, but it does not own the interpretation.',
    ]:
        assert phrase in text
