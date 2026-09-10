from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(root: Path) -> dict:
    input_value = os.environ.get("CCP4_INPUT_PATH")
    if not input_value:
        raise RuntimeError("CCP4_INPUT_PATH is required")

    input_path = Path(input_value).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    df = pd.read_csv(input_path)
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")
    if len(df) < 2:
        raise RuntimeError("Representative fixture must contain at least two bars")

    first_open = float(df.iloc[0]["open"])
    last_close = float(df.iloc[-1]["close"])
    high = float(df["high"].max())
    low = float(df["low"].min())
    total_volume = int(df["volume"].sum())
    return_pct = ((last_close / first_open) - 1.0) * 100.0
    range_pct = ((high / low) - 1.0) * 100.0

    result = {
        "job": "CCP4-REMOTE-FIXTURE",
        "classification": "INFRASTRUCTURE_CERTIFICATION_ONLY",
        "input_sha256": _sha256(input_path),
        "rows": int(len(df)),
        "first_timestamp": str(df.iloc[0]["timestamp"]),
        "last_timestamp": str(df.iloc[-1]["timestamp"]),
        "first_open": round(first_open, 6),
        "last_close": round(last_close, 6),
        "high": round(high, 6),
        "low": round(low, 6),
        "total_volume": total_volume,
        "return_pct": round(return_pct, 6),
        "range_pct": round(range_pct, 6),
    }

    out = root / "research_outputs" / "cloud_compute" / "ccp4" / "remote_job.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["output"] = str(out)
    return result
