from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cloud_compute.autonomous_dispatch import build_dispatch_payload


@dataclass(frozen=True)
class AcceptanceEvidence:
    job_id: str
    git_sha: str
    watcher_discovered: bool
    dispatched_sha: str
    claim_winner_count: int
    execution_status: str
    persisted_status: str
    duplicate_terminal_attempts: int
    stale_recovery_action: str
    recovered_clean_queue: bool
    fixture_terminal_cleanup: bool
    operational_health_status: str


def certify(e: AcceptanceEvidence) -> dict[str, Any]:
    """Fail closed unless the complete governed resilience chain is evidenced."""
    dispatch = build_dispatch_payload(job_id=e.job_id, git_sha=e.git_sha, target_ref=e.git_sha)
    checks = {
        'watcher_discovered': e.watcher_discovered,
        'exact_sha_dispatch': dispatch['git_sha'] == e.git_sha.lower() == e.dispatched_sha.lower(),
        'single_claim_owner': e.claim_winner_count == 1,
        'execution_terminal': e.execution_status == 'succeeded',
        'terminal_persisted': e.persisted_status == 'succeeded',
        'no_duplicate_terminal_execution': e.duplicate_terminal_attempts == 0,
        'stale_recovery_requeues': e.stale_recovery_action == 'requeue',
        'recovery_returns_clean_queue': e.recovered_clean_queue,
        'fixture_cleanup_terminal': e.fixture_terminal_cleanup,
        'operational_health_healthy': e.operational_health_status == 'healthy',
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError('consolidated resilience certification failed: ' + ', '.join(failed))
    return {'status': 'PASS', 'job_id': e.job_id, 'git_sha': e.git_sha.lower(), 'checks': checks}
