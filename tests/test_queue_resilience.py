from datetime import datetime, timedelta, timezone

from cloud_compute.queue_resilience import ResiliencePolicy, classify_job, classify_wakeup_event

NOW = datetime(2026, 9, 23, 23, 0, tzinfo=timezone.utc)
POLICY = ResiliencePolicy()


def test_acknowledged_event_is_complete() -> None:
    assert classify_wakeup_event({"dispatch_status": "acknowledged", "attempt_count": 1}, now=NOW, policy=POLICY) == "complete"


def test_old_pending_event_is_retryable() -> None:
    row = {"dispatch_status": "pending", "attempt_count": 0, "created_at": (NOW - timedelta(minutes=3)).isoformat()}
    assert classify_wakeup_event(row, now=NOW, policy=POLICY) == "retry"


def test_recent_pending_event_waits() -> None:
    row = {"dispatch_status": "pending", "attempt_count": 0, "created_at": (NOW - timedelta(seconds=30)).isoformat()}
    assert classify_wakeup_event(row, now=NOW, policy=POLICY) == "wait"


def test_stuck_requested_event_is_retryable() -> None:
    row = {"dispatch_status": "requested", "attempt_count": 1, "dispatch_requested_at": (NOW - timedelta(minutes=6)).isoformat()}
    assert classify_wakeup_event(row, now=NOW, policy=POLICY) == "retry"


def test_attempt_budget_prevents_infinite_wakeup_retry() -> None:
    row = {"dispatch_status": "failed", "attempt_count": 5, "created_at": (NOW - timedelta(hours=1)).isoformat()}
    assert classify_wakeup_event(row, now=NOW, policy=POLICY) == "exhausted"


def test_queued_job_remains_eligible() -> None:
    assert classify_job({"status": "queued"}, now=NOW, policy=POLICY) == "eligible"


def test_old_running_job_is_classified_stale_not_requeued() -> None:
    row = {"status": "running", "started_at": (NOW - timedelta(minutes=31)).isoformat()}
    assert classify_job(row, now=NOW, policy=POLICY) == "stale_running"


def test_recent_running_job_remains_running() -> None:
    row = {"status": "running", "started_at": (NOW - timedelta(minutes=5)).isoformat()}
    assert classify_job(row, now=NOW, policy=POLICY) == "running"
