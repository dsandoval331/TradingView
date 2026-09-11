from datetime import datetime, timedelta, timezone

from cloud_compute.stale_recovery import decide_stale_recovery, recovery_update

NOW = datetime(2026, 9, 11, 3, 0, tzinfo=timezone.utc)


def _job(**overrides):
    base = {
        "job_id": "job-1",
        "status": "running",
        "assigned_at": (NOW - timedelta(hours=2)).isoformat(),
        "started_at": (NOW - timedelta(hours=2)).isoformat(),
        "parameters_json": {
            "attempt_count": 1,
            "retry_policy": {"enabled": True, "max_attempts": 2, "retry_exit_codes": [1]},
        },
    }
    base.update(overrides)
    return base


def test_non_stale_job_is_not_recovered() -> None:
    job = _job(started_at=(NOW - timedelta(minutes=10)).isoformat())
    d = decide_stale_recovery(job, now=NOW, external_execution_active=False)
    assert d.action == "none"
    assert d.reason == "job_not_stale"


def test_active_external_execution_blocks_recovery() -> None:
    d = decide_stale_recovery(_job(), now=NOW, external_execution_active=True)
    assert d.action == "none"
    assert d.reason == "external_execution_still_active"


def test_unknown_liveness_fails_closed() -> None:
    d = decide_stale_recovery(_job(), now=NOW, external_execution_active=None)
    assert d.action == "none"
    assert d.reason == "external_execution_liveness_unknown"


def test_confirmed_inactive_stale_job_requeues_when_retry_available() -> None:
    d = decide_stale_recovery(_job(), now=NOW, external_execution_active=False)
    assert d.action == "requeue"
    update = recovery_update(d)
    assert update["status"] == "queued"
    assert update["assigned_executor"] is None
    assert update["started_at"] is None


def test_confirmed_inactive_stale_job_quarantines_without_retry() -> None:
    job = _job(parameters_json={"attempt_count": 2, "retry_policy": {"enabled": True, "max_attempts": 2}})
    d = decide_stale_recovery(job, now=NOW, external_execution_active=False)
    assert d.action == "quarantine"
    assert recovery_update(d)["status"] == "failed"


def test_missing_start_time_quarantines() -> None:
    d = decide_stale_recovery(_job(started_at=None, assigned_at=None), now=NOW, external_execution_active=False)
    assert d.action == "quarantine"
    assert d.reason == "running_job_missing_start_time"
