from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class DispatchRequest:
    job_id: str
    git_sha: str
    target_ref: str


def parse_dispatch_request(payload: dict[str, Any]) -> DispatchRequest:
    job_id = str(payload.get("job_id") or "").strip()
    git_sha = str(payload.get("git_sha") or "").strip()
    target_ref = str(payload.get("target_ref") or "").strip()
    if not _UUID_RE.fullmatch(job_id):
        raise ValueError("job_id must be a UUID-shaped control-plane job id")
    if not _SHA_RE.fullmatch(git_sha):
        raise ValueError("git_sha must be an exact 40-character Git SHA")
    if not target_ref or target_ref.startswith("-") or ".." in target_ref:
        raise ValueError("target_ref is invalid")
    return DispatchRequest(job_id=job_id, git_sha=git_sha.lower(), target_ref=target_ref)


def load_dispatch_request(path: Path) -> DispatchRequest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("dispatch request must be a JSON object")
    return parse_dispatch_request(payload)


def build_dispatch_payload(*, job_id: str, git_sha: str, target_ref: str) -> dict[str, str]:
    request = parse_dispatch_request({"job_id": job_id, "git_sha": git_sha, "target_ref": target_ref})
    return {
        "job_id": request.job_id,
        "git_sha": request.git_sha,
        "target_ref": request.target_ref,
    }
