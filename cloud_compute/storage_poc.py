from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

from cloud_compute.manifest import sha256_file

DEFAULT_BUCKET = "trading-research-market-data"
DEFAULT_OBJECTS = (
    "1m/SPY/2025.parquet",
    "1m/SPY/2026.parquet",
    "1m/AAPL/2025.parquet",
)


def _storage_url(project_url: str, endpoint: str, bucket: str, object_path: str) -> str:
    project_url = project_url.rstrip("/")
    return (
        f"{project_url}/storage/v1/{endpoint}/"
        f"{quote(bucket, safe='')}/{quote(object_path, safe='/')}"
    )


def _headers(secret_key: str, *, content_type: str | None = None) -> dict[str, str]:
    """Build Storage headers for both modern and legacy elevated Supabase keys.

    Modern sb_secret_* keys are opaque API keys, not JWTs. Sending them as a
    Bearer token makes Storage try to parse them as JWTs and can fail with
    "Invalid Compact JWS". For modern secret keys, send only the apikey header
    and let Supabase's platform gateway apply the service-role identity.

    Legacy service_role keys are JWTs, so retain the Authorization header for
    backwards compatibility.
    """
    headers = {"apikey": secret_key}
    if not secret_key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {secret_key}"
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _local_entries(cache_root: Path, object_paths: list[str]) -> list[dict]:
    root = cache_root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Cache root does not exist: {root}")

    entries: list[dict] = []
    for rel in object_paths:
        path = root / Path(rel)
        if not path.is_file():
            raise FileNotFoundError(f"POC object is missing locally: {path}")
        entries.append(
            {
                "path": rel.replace("\\", "/"),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "local_path": str(path),
            }
        )
    return entries


def _upload_object(
    project_url: str,
    secret_key: str,
    bucket: str,
    remote_path: str,
    local_path: Path,
    *,
    allow_existing: bool,
) -> str:
    url = _storage_url(project_url, "object", bucket, remote_path)
    with local_path.open("rb") as handle:
        response = requests.post(
            url,
            headers={
                **_headers(secret_key, content_type="application/octet-stream"),
                "x-upsert": "false",
            },
            data=handle,
            timeout=180,
        )

    if response.ok:
        return "UPLOADED"

    body = response.text.lower()
    duplicate = response.status_code in {400, 409} and (
        "duplicate" in body or "already exists" in body or "resource already exists" in body
    )
    if allow_existing and duplicate:
        return "EXISTING"

    raise RuntimeError(
        f"Upload failed for {remote_path}: HTTP {response.status_code} {response.text[:500]}"
    )


def _download_object(
    project_url: str,
    secret_key: str,
    bucket: str,
    remote_path: str,
    destination: Path,
) -> None:
    url = _storage_url(project_url, "object/authenticated", bucket, remote_path)
    with requests.get(url, headers=_headers(secret_key), stream=True, timeout=180) as response:
        if not response.ok:
            raise RuntimeError(
                f"Download failed for {remote_path}: HTTP {response.status_code} {response.text[:500]}"
            )
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def run_poc(
    cache_root: Path,
    object_paths: list[str],
    *,
    project_url: str | None,
    secret_key: str | None,
    bucket: str,
    output: Path,
    dry_run: bool,
    allow_existing: bool,
) -> dict:
    entries = _local_entries(cache_root, object_paths)
    record = {
        "poc_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket,
        "cache_root": str(cache_root.expanduser().resolve()),
        "dry_run": dry_run,
        "status": "PLANNED" if dry_run else "RUNNING",
        "objects": [],
    }

    if not dry_run:
        if not project_url:
            raise RuntimeError("SUPABASE_URL is required for a live POC run")
        if not secret_key:
            raise RuntimeError("SUPABASE_SECRET_KEY is required for a live POC run")

    for entry in entries:
        item = {
            "path": entry["path"],
            "size_bytes": entry["size_bytes"],
            "local_sha256": entry["sha256"],
        }

        if dry_run:
            item["status"] = "READY"
            record["objects"].append(item)
            continue

        local_path = Path(entry["local_path"])
        upload_status = _upload_object(
            project_url,
            secret_key,
            bucket,
            entry["path"],
            local_path,
            allow_existing=allow_existing,
        )

        with tempfile.TemporaryDirectory(prefix="tr-ccp2-") as tmpdir:
            downloaded = Path(tmpdir) / local_path.name
            _download_object(project_url, secret_key, bucket, entry["path"], downloaded)
            remote_sha = sha256_file(downloaded)
            remote_size = downloaded.stat().st_size

        parity = remote_sha == entry["sha256"] and remote_size == entry["size_bytes"]
        item.update(
            {
                "upload_status": upload_status,
                "downloaded_size_bytes": remote_size,
                "downloaded_sha256": remote_sha,
                "parity": parity,
                "status": "PASS" if parity else "FAIL",
            }
        )
        record["objects"].append(item)
        if not parity:
            record["status"] = "FAIL"
            break

    if dry_run:
        record["status"] = "READY"
    elif record["status"] != "FAIL":
        record["status"] = "PASS"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload a small MARKET_CACHE_V1 subset to private Supabase Storage, download it, and prove SHA-256 parity."
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=Path("market_cache/MARKET_CACHE_V1"),
    )
    parser.add_argument(
        "--object",
        dest="objects",
        action="append",
        help="Relative object path beneath MARKET_CACHE_V1. Repeat for multiple objects.",
    )
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research_outputs/cloud_compute/ccp2/storage_poc.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-existing",
        action="store_true",
        help="On reruns, accept a duplicate-object response and verify the existing object instead of overwriting it.",
    )
    args = parser.parse_args()

    objects = args.objects or list(DEFAULT_OBJECTS)
    record = run_poc(
        args.cache_root,
        objects,
        project_url=os.environ.get("SUPABASE_URL"),
        secret_key=os.environ.get("SUPABASE_SECRET_KEY"),
        bucket=args.bucket,
        output=args.output,
        dry_run=args.dry_run,
        allow_existing=args.allow_existing,
    )

    print(f"CCP2_STORAGE_POC={record['status']}")
    print(f"OUTPUT={args.output}")
    for item in record["objects"]:
        print(f"{item['path']}: {item['status']} {item['local_sha256']}")
    return 0 if record["status"] in {"READY", "PASS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
