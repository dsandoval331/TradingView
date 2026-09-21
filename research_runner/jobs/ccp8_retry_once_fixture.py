from __future__ import annotations

import json
from pathlib import Path

from cloud_compute.manifest import sha256_file


def run(work_root: Path) -> dict:
    out_dir = work_root / "research_outputs" / "cloud_compute" / "ccp8"
    out_dir.mkdir(parents=True, exist_ok=True)
    marker = out_dir / "retry_once_marker.txt"
    artifact = out_dir / "retry_once_fixture.json"

    if not marker.exists():
        marker.write_text("first-attempt-failed\n", encoding="utf-8")
        raise RuntimeError("CCP8 deterministic first-attempt failure")

    payload = {
        "fixture": "CCP8-RETRY-ONCE-FIXTURE",
        "result": "PASS_AFTER_RETRY",
        "attempt_behavior": "fail_once_then_succeed",
    }
    artifact.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return {
        "artifact": str(artifact.relative_to(work_root)).replace("\\", "/"),
        "sha256": sha256_file(artifact),
        "result": "PASS_AFTER_RETRY",
    }
