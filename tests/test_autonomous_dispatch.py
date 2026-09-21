import json
from pathlib import Path

import pytest

from cloud_compute.autonomous_dispatch import build_dispatch_payload, load_dispatch_request, parse_dispatch_request

JOB_ID = "11111111-2222-3333-4444-555555555555"
GIT_SHA = "0123456789abcdef0123456789abcdef01234567"
TARGET_REF = "research/example-branch"


def test_valid_dispatch_request_round_trips(tmp_path: Path) -> None:
    payload = build_dispatch_payload(job_id=JOB_ID, git_sha=GIT_SHA, target_ref=TARGET_REF)
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    request = load_dispatch_request(path)
    assert request.job_id == JOB_ID
    assert request.git_sha == GIT_SHA
    assert request.target_ref == TARGET_REF


def test_invalid_sha_fails_closed() -> None:
    with pytest.raises(ValueError, match="exact 40-character Git SHA"):
        parse_dispatch_request({"job_id": JOB_ID, "git_sha": "main", "target_ref": TARGET_REF})


def test_invalid_job_id_fails_closed() -> None:
    with pytest.raises(ValueError, match="UUID-shaped"):
        parse_dispatch_request({"job_id": "not-a-job", "git_sha": GIT_SHA, "target_ref": TARGET_REF})


def test_suspicious_target_ref_fails_closed() -> None:
    with pytest.raises(ValueError, match="target_ref is invalid"):
        parse_dispatch_request({"job_id": JOB_ID, "git_sha": GIT_SHA, "target_ref": "../main"})
