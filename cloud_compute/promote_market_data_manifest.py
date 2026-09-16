from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cloud_compute.manifest import sha256_file
from cloud_compute.storage_poc import DEFAULT_BUCKET, _download_object, _upload_object


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("manifest must contain a non-empty files list")
    return payload


def _new_report(manifest_path: Path, manifest: dict, bucket: str) -> dict:
    return {
        "promotion_version": 1,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "completed_at_utc": None,
        "status": "RUNNING",
        "manifest_path": str(manifest_path),
        "dataset_version": manifest.get("dataset_version"),
        "universe": manifest.get("universe"),
        "bucket": bucket,
        "expected_partitions": len(manifest["files"]),
        "objects": [],
    }


def promote_manifest(
    manifest_path: Path,
    *,
    project_url: str,
    secret_key: str,
    bucket: str,
    output: Path,
    resume: bool,
) -> dict:
    manifest_path = manifest_path.expanduser().resolve()
    output = output.expanduser().resolve()
    manifest = _load_manifest(manifest_path)

    if resume and output.is_file():
        report = json.loads(output.read_text(encoding="utf-8"))
        if report.get("dataset_version") != manifest.get("dataset_version"):
            raise RuntimeError("resume report dataset_version does not match manifest")
        if report.get("universe") != manifest.get("universe"):
            raise RuntimeError("resume report universe does not match manifest")
        if report.get("expected_partitions") != len(manifest["files"]):
            raise RuntimeError("resume report partition count does not match manifest")
        report["status"] = "RUNNING"
    else:
        report = _new_report(manifest_path, manifest, bucket)

    completed = {
        item["object_path"]: item
        for item in report.get("objects", [])
        if item.get("status") == "PASS" and item.get("parity") is True
    }

    for entry in manifest["files"]:
        local_rel = entry["local_relative_path"]
        object_path = entry["storage_object_path"]
        expected_size = int(entry["bytes"])
        expected_sha = str(entry["sha256"]).lower()
        local_path = Path(local_rel).expanduser().resolve()

        prior = completed.get(object_path)
        if prior and prior.get("expected_size_bytes") == expected_size and prior.get("expected_sha256") == expected_sha:
            print(f"SKIP_VERIFIED={object_path}", flush=True)
            continue

        if not local_path.is_file():
            raise FileNotFoundError(f"required manifest input missing: {local_path}")

        local_size = local_path.stat().st_size
        local_sha = sha256_file(local_path)
        if local_size != expected_size or local_sha != expected_sha:
            raise RuntimeError(
                f"local manifest parity failed for {object_path}: "
                f"expected={expected_size}/{expected_sha} actual={local_size}/{local_sha}"
            )

        print(f"PROMOTE={object_path}", flush=True)
        upload_status = _upload_object(
            project_url,
            secret_key,
            bucket,
            object_path,
            local_path,
            allow_existing=True,
        )

        with tempfile.TemporaryDirectory(prefix="tr-ir11-promote-") as tmpdir:
            downloaded = Path(tmpdir) / local_path.name
            _download_object(project_url, secret_key, bucket, object_path, downloaded)
            remote_size = downloaded.stat().st_size
            remote_sha = sha256_file(downloaded)

        parity = remote_size == expected_size and remote_sha == expected_sha
        item = {
            "symbol": entry.get("symbol"),
            "year": entry.get("year"),
            "historical_p1_status": entry.get("historical_p1_status"),
            "object_path": object_path,
            "expected_size_bytes": expected_size,
            "expected_sha256": expected_sha,
            "upload_status": upload_status,
            "remote_size_bytes": remote_size,
            "remote_sha256": remote_sha,
            "parity": parity,
            "status": "PASS" if parity else "FAIL",
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        }

        report["objects"] = [x for x in report.get("objects", []) if x.get("object_path") != object_path]
        report["objects"].append(item)
        report["verified_partitions"] = sum(1 for x in report["objects"] if x.get("status") == "PASS")
        report["verified_bytes"] = sum(int(x.get("expected_size_bytes", 0)) for x in report["objects"] if x.get("status") == "PASS")
        _write_json(output, report)

        if not parity:
            report["status"] = "FAIL"
            _write_json(output, report)
            raise RuntimeError(
                f"remote parity failed for {object_path}: "
                f"expected={expected_size}/{expected_sha} remote={remote_size}/{remote_sha}"
            )

    expected_paths = {entry["storage_object_path"] for entry in manifest["files"]}
    passed_paths = {x["object_path"] for x in report.get("objects", []) if x.get("status") == "PASS" and x.get("parity") is True}
    if passed_paths != expected_paths:
        missing = sorted(expected_paths - passed_paths)
        raise RuntimeError(f"promotion incomplete; missing verified objects: {missing[:10]}")

    report["status"] = "PASS"
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["verified_partitions"] = len(passed_paths)
    report["verified_bytes"] = sum(int(x["expected_size_bytes"]) for x in report["objects"] if x["object_path"] in passed_paths)
    _write_json(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resumably promote a frozen MARKET_CACHE_V1 manifest to private Supabase Storage with byte/SHA parity."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("research_outputs/cloud_compute/ir11_market_data_promotion_manifest.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research_outputs/cloud_compute/ir11_market_data_promotion_report.json"),
    )
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL") or os.environ.get("TR_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("TR_SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL (or TR_SUPABASE_URL) and SUPABASE_SECRET_KEY (or TR_SUPABASE_SECRET_KEY) are required"
        )

    report = promote_manifest(
        args.manifest,
        project_url=url,
        secret_key=key,
        bucket=args.bucket,
        output=args.output,
        resume=not args.no_resume,
    )

    print("IR11_MARKET_DATA_PROMOTION=PASS")
    print(f"PARTITIONS={report['verified_partitions']}")
    print(f"BYTES={report['verified_bytes']}")
    print(f"OUTPUT={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
