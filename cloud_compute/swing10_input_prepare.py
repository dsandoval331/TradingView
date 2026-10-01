"""Bounded SW10-S2-B1 input recovery using existing online credentials.

No research computation, database password, overwrite, or new infrastructure.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path

import pandas as pd

from cloud_compute.control_plane import ControlPlaneConfig, _fetch_rows, create_job_input, fetch_job_inputs
from cloud_compute.storage_poc import DEFAULT_BUCKET, _download_object, _upload_object

JOB_ID = "b355eadf-8cd3-417b-9508-b0d952e858ab"
RESEARCH_SHA = "af73dad08c7edf4b5733a55d61aba0ea5d0cbf66"
DATASET = "market_daily_history_2025-02-03_2026-08-27"
COLUMNS = ["symbol", "trade_date", "open", "high", "low", "close", "volume"]
LOCAL_PATH = "job_inputs/swing10/market_daily_history.csv"


def validate_panel(frame: pd.DataFrame) -> dict:
    if list(frame.columns) != COLUMNS or frame.empty or frame.isna().any().any():
        raise RuntimeError("invalid SW10 panel schema or nulls")
    if frame.duplicated(["symbol", "trade_date"]).any():
        raise RuntimeError("duplicate SW10 symbol/date")
    if (len(frame), frame.symbol.nunique(), frame.trade_date.min(), frame.trade_date.max()) != (44128, 112, "2025-02-03", "2026-08-27"):
        raise RuntimeError("SW10 panel coverage differs from independently certified source")
    prices = frame[["open", "high", "low", "close"]]
    if (prices <= 0).any().any() or (frame.volume < 0).any():
        raise RuntimeError("invalid SW10 prices/volume")
    if (frame.high < prices.max(axis=1)).any() or (frame.low > prices.min(axis=1)).any():
        raise RuntimeError("SW10 OHLC integrity failure")
    return {"row_count": len(frame), "symbol_count": 112, "min_trade_date": frame.trade_date.min(),
            "max_trade_date": frame.trade_date.max(), "symbols": sorted(frame.symbol.unique().tolist()),
            "duplicate_count": 0, "ohlc_integrity": "PASS"}


def export_panel(config: ControlPlaneConfig) -> tuple[bytes, dict]:
    rows = []
    offset = 0
    while True:
        page = _fetch_rows(config, "market_daily_history", {"select": ",".join(COLUMNS),
            "order": "symbol.asc,trade_date.asc", "limit": "1000", "offset": str(offset),
            "trade_date": "gte.2025-02-03", "and": "(trade_date.lte.2026-08-27)"})
        rows.extend(page)
        if len(page) < 1000:
            break
        offset += len(page)
    frame = pd.DataFrame(rows, columns=COLUMNS).sort_values(["symbol", "trade_date"], kind="stable").reset_index(drop=True)
    metadata = validate_panel(frame)
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8"), metadata


def prepare(config: ControlPlaneConfig, job_id: str) -> dict:
    if job_id != JOB_ID:
        raise RuntimeError("input preparation restricted to frozen SW10 job")
    jobs = _fetch_rows(config, "research_jobs", {"job_id": f"eq.{job_id}", "limit": "2"})
    if len(jobs) != 1 or jobs[0]["git_sha"] != RESEARCH_SHA or jobs[0]["dataset_version"] != DATASET or jobs[0]["runner_job_id"] != "SW10-S2-B1":
        raise RuntimeError("frozen SW10 job identity mismatch")
    inputs = fetch_job_inputs(config, job_id)
    with tempfile.TemporaryDirectory(prefix="sw10-input-") as td:
        local = Path(td) / "panel.csv"
        if inputs:
            if len(inputs) != 1:
                raise RuntimeError("unexpected SW10 input count")
            row = inputs[0]
            if row["dataset_version"] != DATASET or (row.get("metadata_json") or {}).get("local_relative_path") != LOCAL_PATH:
                raise RuntimeError("registered SW10 input contract mismatch")
            _download_object(config.supabase_url, config.secret_key, DEFAULT_BUCKET, row["object_path"], local)
            data = local.read_bytes()
            if len(data) != row["object_size_bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise RuntimeError("registered input parity failure")
            validate_panel(pd.read_csv(io.BytesIO(data)))
            return {"status": "VERIFIED_EXISTING", "input_id": row["input_id"], "sha256": row["sha256"], "size_bytes": len(data)}
        data, metadata = export_panel(config)
        second, second_metadata = export_panel(config)
        if data != second or metadata != second_metadata:
            raise RuntimeError("canonical panel changed during export; no input registered")
        digest = hashlib.sha256(data).hexdigest()
        object_path = f"governed_inputs/swing10/s2_b1/{DATASET}/{digest}.csv"
        local.write_bytes(data)
        _upload_object(config.supabase_url, config.secret_key, DEFAULT_BUCKET, object_path, local, allow_existing=True)
        downloaded = Path(td) / "readback.csv"
        _download_object(config.supabase_url, config.secret_key, DEFAULT_BUCKET, object_path, downloaded)
        retrieved = downloaded.read_bytes()
        if len(retrieved) != len(data) or hashlib.sha256(retrieved).hexdigest() != digest:
            raise RuntimeError("immutable input storage parity failure")
        metadata.update({"bucket_name": DEFAULT_BUCKET, "local_relative_path": LOCAL_PATH,
            "source_table": "public.market_daily_history", "source_project_ref": "vrdesbkgxssupfqnrrag",
            "research_sha": RESEARCH_SHA, "mwe_id": "MWE-SW10-S2B1-001",
            "double_export_byte_parity": True, "storage_readback_verified": True,
            "preparation_infrastructure_sha": os.environ.get("GITHUB_SHA"),
            "preparation_github_run": os.environ.get("GITHUB_RUN_ID")})
        row = create_job_input(config, {"job_id": job_id, "input_type": "market_data",
            "dataset_version": DATASET, "object_path": object_path, "object_size_bytes": len(data),
            "sha256": digest, "required": True, "metadata_json": metadata})
        registered = fetch_job_inputs(config, job_id)
        if len(registered) != 1 or registered[0]["input_id"] != row["input_id"] or registered[0]["sha256"] != digest or registered[0]["object_size_bytes"] != len(data):
            raise RuntimeError("input registration readback mismatch")
        return {"status": "PASS", "input_id": row["input_id"], "object_path": object_path,
                "size_bytes": len(data), "sha256": digest, **metadata}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    result = prepare(ControlPlaneConfig(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"]), args.job_id)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
