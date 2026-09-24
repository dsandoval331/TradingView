from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from cloud_compute.control_plane import ControlPlaneConfig, _fetch_rows


@dataclass(frozen=True)
class ResiliencePolicy:
    pending_retry_after: timedelta = timedelta(minutes=2)
    requested_retry_after: timedelta = timedelta(minutes=5)
    failed_retry_after: timedelta = timedelta(minutes=2)
    running_stale_after: timedelta = timedelta(minutes=30)
    max_wakeup_attempts: int = 5


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def classify_wakeup_event(row: dict[str, Any], *, now: datetime, policy: ResiliencePolicy) -> str:
    status = str(row.get("dispatch_status") or "")
    attempts = int(row.get("attempt_count") or 0)
    if status == "acknowledged":
        return "complete"
    if attempts >= policy.max_wakeup_attempts:
        return "exhausted"
    created = _dt(row.get("created_at"))
    requested = _dt(row.get("dispatch_requested_at"))
    if status == "pending" and created and now - created >= policy.pending_retry_after:
        return "retry"
    if status == "requested" and requested and now - requested >= policy.requested_retry_after:
        return "retry"
    if status == "failed":
        anchor = requested or created
        if anchor and now - anchor >= policy.failed_retry_after:
            return "retry"
    return "wait"


def classify_job(row: dict[str, Any], *, now: datetime, policy: ResiliencePolicy) -> str:
    status = str(row.get("status") or "")
    if status == "queued":
        return "eligible"
    if status != "running":
        return "terminal_or_ineligible"
    started = _dt(row.get("started_at"))
    if started and now - started >= policy.running_stale_after:
        return "stale_running"
    return "running"


def fetch_wakeup_events(config: ControlPlaneConfig, *, limit: int = 100) -> list[dict[str, Any]]:
    return _fetch_rows(config, "research_queue_wakeup_events", {
        "dispatch_status": "in.(pending,requested,failed)",
        "order": "created_at.asc",
        "limit": str(limit),
    })


def fetch_running_jobs(config: ControlPlaneConfig, *, limit: int = 100) -> list[dict[str, Any]]:
    return _fetch_rows(config, "research_jobs", {
        "status": "eq.running",
        "order": "started_at.asc",
        "limit": str(limit),
    })


def fetch_job_attempts(config: ControlPlaneConfig, job_id: str) -> list[dict[str, Any]]:
    return _fetch_rows(config, "research_job_attempts", {
        "job_id": f"eq.{job_id}",
        "order": "attempt_no.desc",
    })


def reconcile_wakeup_events(
    config: ControlPlaneConfig,
    *,
    wake: Callable[[dict[str, Any]], None],
    now: datetime | None = None,
    policy: ResiliencePolicy | None = None,
    limit: int = 100,
) -> dict[str, int]:
    """Retry stale wake-up notifications only; never mutate research_jobs."""
    now = now or datetime.now(timezone.utc)
    policy = policy or ResiliencePolicy()
    counts = {"retry": 0, "wait": 0, "exhausted": 0, "complete": 0}
    for event in fetch_wakeup_events(config, limit=limit):
        action = classify_wakeup_event(event, now=now, policy=policy)
        counts[action] = counts.get(action, 0) + 1
        if action == "retry":
            wake(event)
    return counts


def evaluate_running_job_ownership(
    job: dict[str, Any],
    attempts: list[dict[str, Any]],
    *,
    now: datetime,
    policy: ResiliencePolicy,
) -> str:
    """Classify ownership safety. This function never changes job state."""
    if classify_job(job, now=now, policy=policy) != "stale_running":
        return "not_stale"
    if not attempts:
        return "stale_no_attempt_escalate"
    latest = attempts[0]
    if str(latest.get("status") or "") == "running":
        return "stale_owned_escalate"
    return "stale_ownership_inconsistent_escalate"


def reconcile_running_jobs(
    config: ControlPlaneConfig,
    *,
    now: datetime | None = None,
    policy: ResiliencePolicy | None = None,
    limit: int = 100,
) -> dict[str, int]:
    """Detect stale ownership; deliberately performs no automatic requeue."""
    now = now or datetime.now(timezone.utc)
    policy = policy or ResiliencePolicy()
    counts: dict[str, int] = {}
    for job in fetch_running_jobs(config, limit=limit):
        attempts = fetch_job_attempts(config, str(job["job_id"]))
        action = evaluate_running_job_ownership(job, attempts, now=now, policy=policy)
        counts[action] = counts.get(action, 0) + 1
    return counts
