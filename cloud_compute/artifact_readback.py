from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

import requests

from cloud_compute.control_plane import ControlPlaneConfig, _fetch_rows, _request_headers
from cloud_compute.storage_poc import _download_object

MAX_TEXT_BYTES = 10 * 1024 * 1024


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _upsert(config: ControlPlaneConfig, payload: dict) -> dict:
    response = requests.post(
        f"{config.rest_url}/research_artifact_readbacks",
        params={"on_conflict": "artifact_id"},
        headers=_request_headers(
            config.secret_key,
            prefer="resolution=merge-duplicates,return=representation",
        ),
        json=payload,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"readback upsert failed: HTTP {response.status_code} {response.text[:500]}")
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("readback upsert expected exactly one row")
    return rows[0]


def run(job_id: str, names: list[str] | None = None) -> dict:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SECRET_KEY"]
    readback_sha = os.environ.get("TR_GIT_SHA")
    config = ControlPlaneConfig(url, key)

    jobs = _fetch_rows(config, "research_jobs", {"job_id": f"eq.{job_id}", "limit": "2"})
    if len(jobs) != 1 or jobs[0].get("status") != "succeeded":
        raise RuntimeError("source research job must exist and be succeeded")
    source_sha = jobs[0].get("git_sha")

    artifacts = _fetch_rows(config, "research_job_artifacts", {
        "job_id": f"eq.{job_id}",
        "order": "created_at.asc,artifact_id.asc",
    })
    wanted = set(names or [])
    if wanted:
        artifacts = [a for a in artifacts if Path(a["object_path"]).name in wanted]
        found = {Path(a["object_path"]).name for a in artifacts}
        missing = sorted(wanted - found)
        if missing:
            raise RuntimeError(f"requested artifacts not registered: {missing}")

    rows = []
    for artifact in artifacts:
        name = Path(artifact["object_path"]).name
        size = int(artifact["size_bytes"])
        if size > MAX_TEXT_BYTES:
            raise RuntimeError(f"artifact exceeds governed text-readback limit ({MAX_TEXT_BYTES} bytes): {name}")
        with tempfile.TemporaryDirectory(prefix="tr-artifact-readback-") as td:
            local = Path(td) / name
            _download_object(url, key, artifact["bucket_name"], artifact["object_path"], local)
            actual_size = local.stat().st_size
            actual_sha = _sha256(local)
            if actual_size != size or actual_sha != artifact["sha256"]:
                raise RuntimeError(f"artifact parity failure: {name}")
            try:
                content = local.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise RuntimeError(f"artifact is not UTF-8 text: {name}") from exc

        payload = {
            "artifact_id": artifact["artifact_id"],
            "job_id": job_id,
            "bucket_name": artifact["bucket_name"],
            "object_path": artifact["object_path"],
            "media_type": artifact.get("media_type"),
            "size_bytes": size,
            "sha256": artifact["sha256"],
            "content_text": content,
            "content_encoding": "utf-8",
            "source_git_sha": source_sha,
            "readback_git_sha": readback_sha,
            "verified_sha256": True,
            "metadata_json": {
                "mechanism": "governed_private_storage_text_readback_v1",
                "source_job_status": "succeeded",
            },
        }
        row = _upsert(config, payload)
        rows.append({"artifact_id": row["artifact_id"], "name": name, "size_bytes": size, "sha256": actual_sha})

    return {"job_id": job_id, "source_git_sha": source_sha, "readback_git_sha": readback_sha, "count": len(rows), "artifacts": rows}


def main() -> int:
    p = argparse.ArgumentParser(description="Checksum-verified readback of private Supabase research artifacts into governed SQL text cache.")
    p.add_argument("--job-id", required=True)
    p.add_argument("--name", action="append", dest="names")
    args = p.parse_args()
    result = run(args.job_id, args.names)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
