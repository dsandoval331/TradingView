from datetime import datetime, timedelta, timezone

from cloud_compute.reliability_audit import audit_jobs, summarize_findings


def _now():
    return datetime(2026, 9, 10, 21, 0, tzinfo=timezone.utc)


def test_clean_succeeded_github_job_has_no_findings() -> None:
    jobs = [{
        "job_id": "job-ok",
        "status": "succeeded",
        "preferred_executor": "github_actions",
        "assigned_executor": "github_actions",
        "cloud_run_spend_approved": False,
        "started_at": (_now() - timedelta(seconds=10)).isoformat(),
        "completed_at": _now().isoformat(),
    }]
    assert audit_jobs(jobs, now=_now()) == []


def test_detects_stale_running_job() -> None:
    jobs = [{
        "job_id": "job-stale",
        "status": "running",
        "preferred_executor": "github_actions",
        "assigned_executor": "github_actions",
        "cloud_run_spend_approved": False,
        "started_at": (_now() - timedelta(hours=2)).isoformat(),
    }]
    findings = audit_jobs(jobs, now=_now(), stale_after_seconds=3600)
    assert [f.code for f in findings] == ["STALE_RUNNING_JOB"]
    assert findings[0].severity == "WARN"


def test_cloud_run_without_explicit_approval_fails_closed() -> None:
    jobs = [{
        "job_id": "job-cloud-run",
        "status": "queued",
        "preferred_executor": "cloud_run",
        "assigned_executor": None,
        "cloud_run_spend_approved": False,
    }]
    findings = audit_jobs(jobs, now=_now())
    assert any(f.code == "CLOUD_RUN_WITHOUT_APPROVAL" and f.severity == "ERROR" for f in findings)


def test_assigned_cloud_run_without_approval_is_error() -> None:
    jobs = [{
        "job_id": "job-cloud-run-assigned",
        "status": "running",
        "preferred_executor": "github_actions",
        "assigned_executor": "cloud_run",
        "cloud_run_spend_approved": False,
        "started_at": _now().isoformat(),
    }]
    findings = audit_jobs(jobs, now=_now())
    assert any(f.code == "CLOUD_RUN_EXECUTED_WITHOUT_APPROVAL" for f in findings)


def test_terminal_state_timestamp_and_summary() -> None:
    jobs = [
        {"job_id": "job-1", "status": "succeeded", "preferred_executor": "github_actions", "completed_at": None},
        {"job_id": "job-2", "status": "failed", "preferred_executor": "github_actions", "completed_at": None},
    ]
    findings = audit_jobs(jobs, now=_now())
    summary = summarize_findings(findings)
    assert summary == {"total": 2, "errors": 1, "warnings": 1}
