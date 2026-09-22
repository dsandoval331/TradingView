from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    reason: str
    job_id: str | None


def _parse_ts(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def decide_stale_recovery(
    job: dict[str, Any],
    *,
    now: datetime | None = None,
    stale_after_seconds: int = 3600,
    external_execution_active: bool | None,
) -> RecoveryDecision:
    """Choose a safe recovery action for one potentially stale running job.

    Fail-closed policy:
    - never mutate a non-running job;
    - never recover a job whose external execution is confirmed active;
    - never recover when executor liveness is unknown;
    - only requeue when liveness is confirmed inactive and retry policy allows it;
    - otherwise quarantine for explicit review.
    """
    job_id = str(job.get("job_id") or "") or None
    status = str(job.get("status") or "").strip().lower()
    if status != "running":
        return RecoveryDecision("none", "job_not_running", job_id)

    started = _parse_ts(job.get("started_at")) or _parse_ts(job.get("assigned_at"))
    if started is None:
        return RecoveryDecision("quarantine", "running_job_missing_start_time", job_id)

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = (now - started).total_seconds()
    if age <= stale_after_seconds:
        return RecoveryDecision("none", "job_not_stale", job_id)

    if external_execution_active is True:
        return RecoveryDecision("none", "external_execution_still_active", job_id)
    if external_execution_active is None:
        return RecoveryDecision("none", "external_execution_liveness_unknown", job_id)

    params = job.get("parameters_json") or {}
    retry = params.get("retry_policy") or {}
    enabled = bool(retry.get("enabled", False)) if isinstance(retry, dict) else False
    max_attempts = int(retry.get("max_attempts", 1)) if isinstance(retry, dict) else 1
    attempt_count = int(params.get("attempt_count", 0) or 0)

    if enabled and attempt_count < max_attempts:
        return RecoveryDecision("requeue", "stale_execution_confirmed_inactive_retry_available", job_id)
    return RecoveryDecision("quarantine", "stale_execution_confirmed_inactive_no_retry_available", job_id)


def recovery_update(decision: RecoveryDecision) -> dict[str, Any]:
    if decision.action == "requeue":
        return {
            "status": "queued",
            "assigned_executor": None,
            "assigned_at": None,
            "started_at": None,
            "completed_at": None,
            "last_error": f"CCP-11 stale recovery: {decision.reason}",
        }
    if decision.action == "quarantine":
        return {
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "last_error": f"CCP-11 stale recovery quarantine: {decision.reason}",
        }
    return {}
