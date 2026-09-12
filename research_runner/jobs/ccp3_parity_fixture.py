from __future__ import annotations

import hashlib
import json
from pathlib import Path


def run(root: Path) -> dict:
    output_dir = root / "research_outputs" / "cloud_compute" / "ccp3"
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "fixture": "CCP3_RUNNER_PARITY_V1",
        "values": [2, 3, 5, 7, 11],
        "sum": 28,
        "product": 2310,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    output = output_dir / "runner_parity_fixture.json"
    output.write_text(canonical, encoding="utf-8")
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "artifact": str(output.relative_to(root)).replace("\\", "/"),
        "sha256": digest,
        "fixture": payload["fixture"],
    }
