from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.queue_resilience import (
    ResiliencePolicy,
    classify_job,
    classify_wakeup_event,
    evaluate_running_job_ownership,
    reconcile_running_jobs,
    reconcile_wakeup_events,
)

NOW = datetime(2026, 9, 23, 23, 0, tzinfo=timezone.utc)
POLICY = ResiliencePolicy()
CONFIG = ControlPlaneConfig("https://example.supabase.co", "secret")


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


def test_failed_dispatch_is_retryable_after_backoff() -> None:
    row = {"dispatch_status": "failed", "attempt_count": 1, "created_at": (NOW - timedelta(minutes=3)).isoformat(), "last_error": "github 503"}
    assert classify_wakeup_event(row, now=NOW, policy=POLICY) == "retry"


def test_failed_dispatch_waits_during_backoff() -> None:
    row = {"dispatch_status": "failed", "attempt_count": 1, "created_at": (NOW - timedelta(seconds=30)).isoformat(), "last_error": "github 503"}
    assert classify_wakeup_event(row, now=NOW, policy=POLICY) == "wait"


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


def test_reconciler_retries_notification_without_updating_research_job() -> None:
    event = {"event_id": "e1", "job_id": "j1", "dispatch_status": "pending", "attempt_count": 0, "created_at": (NOW - timedelta(minutes=3)).isoformat()}
    wake_calls = []
    with patch("cloud_compute.queue_resilience.fetch_wakeup_events", return_value=[event]):
        result = reconcile_wakeup_events(CONFIG, wake=wake_calls.append, now=NOW, policy=POLICY)
    assert result["retry"] == 1
    assert wake_calls == [event]


def test_wakeup_transport_failure_propagates_without_job_mutation() -> None:
    event = {"event_id": "e1", "job_id": "j1", "dispatch_status": "pending", "attempt_count": 0, "created_at": (NOW - timedelta(minutes=3)).isoformat()}
    def fail_wake(_: dict) -> None:
        raise RuntimeError("simulated github dispatch outage")
    with patch("cloud_compute.queue_resilience.fetch_wakeup_events", return_value=[event]):
        with pytest.raises(RuntimeError, match="simulated github dispatch outage"):
            reconcile_wakeup_events(CONFIG, wake=fail_wake, now=NOW, policy=POLICY)


def test_concurrent_duplicate_wakeups_are_notifications_not_job_mutations() -> None:
    event = {"event_id": "e1", "job_id": "j1", "dispatch_status": "pending", "attempt_count": 0, "created_at": (NOW - timedelta(minutes=3)).isoformat()}
    calls = []
    with patch("cloud_compute.queue_resilience.fetch_wakeup_events", return_value=[event]):
        reconcile_wakeup_events(CONFIG, wake=calls.append, now=NOW, policy=POLICY)
        reconcile_wakeup_events(CONFIG, wake=calls.append, now=NOW, policy=POLICY)
    assert calls == [event, event]


def test_stale_running_with_running_attempt_escalates_without_requeue() -> None:
    job = {"job_id": "j1", "status": "running", "started_at": (NOW - timedelta(minutes=31)).isoformat()}
    attempts = [{"attempt_no": 1, "status": "running", "external_execution_id": "gh-1"}]
    assert evaluate_running_job_ownership(job, attempts, now=NOW, policy=POLICY) == "stale_owned_escalate"


def test_stale_running_without_attempt_escalates() -> None:
    job = {"job_id": "j1", "status": "running", "started_at": (NOW - timedelta(minutes=31)).isoformat()}
    assert evaluate_running_job_ownership(job, [], now=NOW, policy=POLICY) == "stale_no_attempt_escalate"


def test_stale_running_with_terminal_attempt_is_inconsistent_not_requeued() -> None:
    job = {"job_id": "j1", "status": "running", "started_at": (NOW - timedelta(minutes=31)).isoformat()}
    attempts = [{"attempt_no": 2, "status": "failed", "external_execution_id": "gh-old"}]
    assert evaluate_running_job_ownership(job, attempts, now=NOW, policy=POLICY) == "stale_ownership_inconsistent_escalate"


def test_running_reconciler_is_read_only() -> None:
    job = {"job_id": "j1", "status": "running", "started_at": (NOW - timedelta(minutes=31)).isoformat()}
    attempt = {"attempt_no": 1, "status": "running"}
    with (
        patch("cloud_compute.queue_resilience.fetch_running_jobs", return_value=[job]),
        patch("cloud_compute.queue_resilience.fetch_job_attempts", return_value=[attempt]),
    ):
        result = reconcile_running_jobs(CONFIG, now=NOW, policy=POLICY)
    assert result == {"stale_owned_escalate": 1}
