from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cloud_compute.manifest import sha256_file
from cloud_compute.storage_poc import DEFAULT_BUCKET, _download_object, _upload_object

DEFAULT_SOURCE = Path("research_outputs/pmpd/post9n_batch1/context_enriched.parquet")
DEFAULT_OBJECT_PATH = "upstream/pmpd/post9n_batch1/context_enriched.parquet"


def promote(
    source: Path,
    *,
    project_url: str,
    secret_key: str,
    bucket: str = DEFAULT_BUCKET,
    object_path: str = DEFAULT_OBJECT_PATH,
    allow_existing: bool = True,
) -> dict:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"canonical artifact not found: {source}")

    size = source.stat().st_size
    digest = sha256_file(source)
    upload_status = _upload_object(
        project_url,
        secret_key,
        bucket,
        object_path,
        source,
        allow_existing=allow_existing,
    )

    with tempfile.TemporaryDirectory(prefix="tr-ccp10-promote-") as tmpdir:
        downloaded = Path(tmpdir) / source.name
        _download_object(project_url, secret_key, bucket, object_path, downloaded)
        remote_size = downloaded.stat().st_size
        remote_sha = sha256_file(downloaded)

    if remote_size != size or remote_sha != digest:
        raise RuntimeError(
            f"promoted artifact parity failed: local={size}/{digest} remote={remote_size}/{remote_sha}"
        )

    return {
        "promotion_version": 1,
        "promoted_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source),
        "bucket_name": bucket,
        "object_path": object_path,
        "size_bytes": size,
        "sha256": digest,
        "upload_status": upload_status,
        "parity": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote an existing canonical research artifact into private Supabase Storage and prove byte/hash parity."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--object-path", default=DEFAULT_OBJECT_PATH)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research_outputs/cloud_compute/ccp10/pmpd_post9n_batch1_promotion.json"),
    )
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")

    record = promote(
        args.source,
        project_url=url,
        secret_key=key,
        bucket=args.bucket,
        object_path=args.object_path,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("CCP10_CANONICAL_ARTIFACT_PROMOTION=PASS")
    print(f"SOURCE={record['source_path']}")
    print(f"OBJECT_PATH={record['object_path']}")
    print(f"SIZE_BYTES={record['size_bytes']}")
    print(f"SHA256={record['sha256']}")
    print(f"OUTPUT={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
