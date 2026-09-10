from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

ALLOWED_EXECUTORS = {"github_actions", "cloud_run", "local_windows"}
ZERO_SPEND_PRIMARY_EXECUTOR = "github_actions"


@dataclass(frozen=True)
class ReliabilityFinding:
    code: str
    severity: str
    job_id: str | None
    message: str


def _parse_ts(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def audit_jobs(
    jobs: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    stale_after_seconds: int = 3600,
) -> list[ReliabilityFinding]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    findings: list[ReliabilityFinding] = []

    for job in jobs:
        job_id = str(job.get("job_id") or "") or None
        status = str(job.get("status") or "").strip().lower()
        preferred = str(job.get("preferred_executor") or "").strip()
        assigned = str(job.get("assigned_executor") or "").strip()
        cloud_spend = bool(job.get("cloud_run_spend_approved", False))

        if preferred and preferred not in ALLOWED_EXECUTORS:
            findings.append(ReliabilityFinding(
                "UNSUPPORTED_PREFERRED_EXECUTOR", "ERROR", job_id,
                f"unsupported preferred executor: {preferred}",
            ))
        if assigned and assigned not in ALLOWED_EXECUTORS:
            findings.append(ReliabilityFinding(
                "UNSUPPORTED_ASSIGNED_EXECUTOR", "ERROR", job_id,
                f"unsupported assigned executor: {assigned}",
            ))
        if preferred == "cloud_run" and not cloud_spend:
            findings.append(ReliabilityFinding(
                "CLOUD_RUN_WITHOUT_APPROVAL", "ERROR", job_id,
                "Cloud Run is preferred without explicit spend approval",
            ))
        if assigned == "cloud_run" and not cloud_spend:
            findings.append(ReliabilityFinding(
                "CLOUD_RUN_EXECUTED_WITHOUT_APPROVAL", "ERROR", job_id,
                "Cloud Run was assigned without explicit spend approval",
            ))

        if status == "running":
            started = _parse_ts(job.get("started_at")) or _parse_ts(job.get("assigned_at"))
            if started is None:
                findings.append(ReliabilityFinding(
                    "RUNNING_WITHOUT_START_TIME", "ERROR", job_id,
                    "running job has neither started_at nor assigned_at",
                ))
            else:
                age = (now - started).total_seconds()
                if age > stale_after_seconds:
                    findings.append(ReliabilityFinding(
                        "STALE_RUNNING_JOB", "WARN", job_id,
                        f"running job age {int(age)}s exceeds stale threshold {stale_after_seconds}s",
                    ))

        if status == "succeeded" and not job.get("completed_at"):
            findings.append(ReliabilityFinding(
                "SUCCEEDED_WITHOUT_COMPLETION_TIME", "ERROR", job_id,
                "succeeded job is missing completed_at",
            ))
        if status == "failed" and not job.get("completed_at"):
            findings.append(ReliabilityFinding(
                "FAILED_WITHOUT_COMPLETION_TIME", "WARN", job_id,
                "failed job is missing completed_at",
            ))

    return findings


def summarize_findings(findings: Iterable[ReliabilityFinding]) -> dict[str, int]:
    rows = list(findings)
    return {
        "total": len(rows),
        "errors": sum(1 for row in rows if row.severity == "ERROR"),
        "warnings": sum(1 for row in rows if row.severity == "WARN"),
    }
