from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class ExecutorLiveness:
    active: bool | None
    status: str | None
    conclusion: str | None
    reason: str


def github_actions_liveness(*, repository: str, run_id: str, token: str | None = None, timeout: int = 20) -> ExecutorLiveness:
    if not repository or not run_id:
        return ExecutorLiveness(None, None, None, "missing_repository_or_run_id")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(
        f"https://api.github.com/repos/{repository}/actions/runs/{run_id}",
        headers=headers,
        timeout=timeout,
    )
    if response.status_code == 404:
        return ExecutorLiveness(None, None, None, "run_not_found")
    if not response.ok:
        return ExecutorLiveness(None, None, None, f"github_http_{response.status_code}")
    body: dict[str, Any] = response.json()
    status = str(body.get("status") or "").lower() or None
    conclusion = str(body.get("conclusion") or "").lower() or None
    if status == "completed":
        return ExecutorLiveness(False, status, conclusion, "github_run_completed")
    if status in {"queued", "in_progress", "requested", "waiting", "pending"}:
        return ExecutorLiveness(True, status, conclusion, "github_run_active")
    return ExecutorLiveness(None, status, conclusion, "github_run_status_unknown")
