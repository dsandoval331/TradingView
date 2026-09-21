from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from cloud_compute.manifest import sha256_file


def run(root: Path) -> dict:
    source = root / "market_cache" / "MARKET_CACHE_V1" / "1m" / "SPY" / "2025.parquet"
    if not source.is_file():
        raise FileNotFoundError(source)

    frame = pd.read_parquet(source)
    out = root / "research_outputs" / "cloud_compute" / "ccp10" / "market_data_input_fixture.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fixture": "CCP10-MARKET-DATA-INPUT",
        "source": "market_cache/MARKET_CACHE_V1/1m/SPY/2025.parquet",
        "source_sha256": sha256_file(source),
        "rows": int(len(frame)),
        "columns": [str(c) for c in frame.columns],
        "status": "PASS",
    }
    out.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return {"artifact": str(out.relative_to(root)).replace("\\", "/"), "sha256": sha256_file(out), "result": payload}
