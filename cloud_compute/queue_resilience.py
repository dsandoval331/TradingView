from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


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
