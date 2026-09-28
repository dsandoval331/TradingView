import pytest

from cloud_compute.consolidated_resilience_cert import AcceptanceEvidence, certify

JOB = '11111111-1111-1111-1111-111111111111'
SHA = 'a' * 40


def evidence(**changes):
    values = dict(
        job_id=JOB, git_sha=SHA, watcher_discovered=True, dispatched_sha=SHA,
        claim_winner_count=1, execution_status='succeeded', persisted_status='succeeded',
        duplicate_terminal_attempts=0, stale_recovery_action='requeue',
        recovered_clean_queue=True, fixture_terminal_cleanup=True,
        operational_health_status='healthy',
    )
    values.update(changes)
    return AcceptanceEvidence(**values)


def test_complete_chain_passes():
    result = certify(evidence())
    assert result['status'] == 'PASS'
    assert all(result['checks'].values())


@pytest.mark.parametrize(('field', 'bad'), [
    ('watcher_discovered', False),
    ('dispatched_sha', 'b' * 40),
    ('claim_winner_count', 2),
    ('execution_status', 'failed'),
    ('persisted_status', 'running'),
    ('duplicate_terminal_attempts', 1),
    ('stale_recovery_action', 'escalate'),
    ('recovered_clean_queue', False),
    ('fixture_terminal_cleanup', False),
    ('operational_health_status', 'attention'),
])
def test_each_acceptance_gate_fails_closed(field, bad):
    with pytest.raises(RuntimeError, match='consolidated resilience certification failed'):
        certify(evidence(**{field: bad}))
