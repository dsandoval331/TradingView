from __future__ import annotations

import argparse
import base64
import math
import hashlib
import json
import os
import tempfile
from pathlib import Path

import requests

from cloud_compute.control_plane import ControlPlaneConfig, _fetch_rows, _request_headers
from cloud_compute.storage_poc import _download_object
from cloud_compute.streaming_artifacts import sql_encode, verify_sql, verify, CHUNK
from cloud_compute.control_plane import _update_one

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
        timeout=180,
    )
    if not response.ok:
        raise RuntimeError(f"readback upsert failed: HTTP {response.status_code} {response.text[:500]}")
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("readback upsert expected exactly one row")
    return rows[0]


def _save_chunk(config,payload):
    response=requests.post(f"{config.rest_url}/research_artifact_readback_chunks",
        params={"on_conflict":"artifact_id,chunk_no"},
        headers=_request_headers(config.secret_key,prefer="resolution=ignore-duplicates,return=minimal"),json=payload,timeout=60)
    if not response.ok:raise RuntimeError(f"lossless readback chunk insert failed: HTTP {response.status_code}")

def _chunk_plan(path):
    chunks=[]
    with Path(path).open('rb') as f:
        for number,data in enumerate(iter(lambda:f.read(CHUNK),b'')):
            chunks.append({'chunk_no':number,'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    return chunks

def _persist_chunks(config,artifact,path,plan):
    with Path(path).open('rb') as f:
        for expected in plan:
            data=f.read(CHUNK)
            if len(data)!=expected['size_bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:raise RuntimeError('source chunk drift')
            _save_chunk(config,{'artifact_id':artifact['artifact_id'],**expected,'content_base64':base64.b64encode(data).decode('ascii')})

def _verify_chunks(config,row,artifact,destination):
    meta=row['metadata_json'];plan=meta['chunks']
    if len(plan)!=math.ceil(int(artifact['size_bytes'])/CHUNK) or [p['chunk_no'] for p in plan]!=list(range(len(plan))):raise RuntimeError('complete contiguous bounded SQL chunk plan required')
    with Path(destination).open('wb') as f:
        for expected in plan:
            found=_fetch_rows(config,'research_artifact_readback_chunks',{'artifact_id':f"eq.{artifact['artifact_id']}",'chunk_no':f"eq.{expected['chunk_no']}",'limit':'2'})
            if len(found)!=1:raise RuntimeError('missing/duplicated durable SQL chunk')
            item=found[0];data=base64.b64decode(item['content_base64'],validate=True)
            if item['chunk_no']!=expected['chunk_no'] or item['size_bytes']!=expected['size_bytes'] or item['sha256']!=expected['sha256'] or len(data)!=expected['size_bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:raise RuntimeError('durable chunk byte parity failure')
            f.write(data)
    return verify(destination,artifact)


def run(job_id: str, names: list[str] | None = None, *, attempt_id: str | None = None) -> dict:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SECRET_KEY"]
    readback_sha = os.environ.get("TR_GIT_SHA")
    config = ControlPlaneConfig(url, key)

    jobs = _fetch_rows(config, "research_jobs", {"job_id": f"eq.{job_id}", "limit": "2"})
    if len(jobs) != 1 or jobs[0].get("status") != "succeeded":
        raise RuntimeError("source research job must exist and be succeeded")
    source_sha = jobs[0].get("git_sha")

    filters = {
        "job_id": f"eq.{job_id}",
        "order": "created_at.asc,artifact_id.asc",
    }
    if attempt_id is not None:
        attempts = _fetch_rows(config, "research_job_attempts", {
            "job_id": f"eq.{job_id}", "attempt_id": f"eq.{attempt_id}", "limit": "2",
        })
        if len(attempts) != 1 or attempts[0].get("status") != "succeeded" or attempts[0].get("git_sha") != source_sha:
            raise RuntimeError("readback attempt must belong to the succeeded exact-revision job")
        filters["attempt_id"] = f"eq.{attempt_id}"
    artifacts = _fetch_rows(config, "research_job_artifacts", filters)
    wanted = set(names or [])
    if wanted:
        artifacts = [a for a in artifacts if (a.get("metadata_json", {}).get("logical_name") or Path(a["object_path"]).name) in wanted]
        found = {a.get("metadata_json", {}).get("logical_name") or Path(a["object_path"]).name for a in artifacts}
        missing = sorted(wanted - found)
        if missing:
            raise RuntimeError(f"requested artifacts not registered: {missing}")

    rows = []
    for artifact in artifacts:
        name = artifact.get("metadata_json", {}).get("logical_name") or Path(artifact["object_path"]).name
        size = int(artifact["size_bytes"])
        if size > MAX_TEXT_BYTES and (artifact.get("metadata_json") or {}).get("storage_encoding") != "gzip":
            raise RuntimeError(f"artifact exceeds governed text-readback limit ({MAX_TEXT_BYTES} bytes): {name}")
        with tempfile.TemporaryDirectory(prefix="tr-artifact-readback-") as td:
            local = Path(td) / name
            _download_object(url, key, artifact["bucket_name"], artifact["object_path"], local)
            actual_size = local.stat().st_size
            actual_sha = _sha256(local)
            if actual_size != size or actual_sha != artifact["sha256"]:
                raise RuntimeError(f"artifact parity failure: {name}")
            chunked=(artifact.get('metadata_json') or {}).get('storage_encoding')=='gzip'
            if chunked:
                _,logical=verify(local,artifact);plan=_chunk_plan(local)
                content=json.dumps({'complete_bytes_in':'research_artifact_readback_chunks','artifact_id':artifact['artifact_id'],'chunk_count':len(plan),'size_bytes':size,'sha256':actual_sha},sort_keys=True)
                encoding='base64+gzip-chunks-v1'
            else:
                content,encoding,logical=sql_encode(local,artifact)
                plan=[]
            # Keep private bytes available through bounded SQL persistence.
            staged=tempfile.NamedTemporaryFile(prefix='tr-verified-readback-',delete=False)
            staged.close()
            import shutil
            shutil.copyfile(local,staged.name)

        payload = {
            "artifact_id": artifact["artifact_id"],
            "job_id": job_id,
            "bucket_name": artifact["bucket_name"],
            "object_path": artifact["object_path"],
            "media_type": artifact.get("media_type"),
            "size_bytes": size,
            "sha256": artifact["sha256"],
            "content_text": content,
            "content_encoding": encoding,
            "source_git_sha": source_sha,
            "readback_git_sha": readback_sha,
            "verified_sha256": not chunked,
            "metadata_json": {
                "mechanism": "governed_lossless_private_storage_sql_readback_v2",
                "logical_sha256": logical["sha256"], "logical_size_bytes": logical["size_bytes"],
                "storage_encoding": (artifact.get("metadata_json") or {}).get("storage_encoding", "identity"),
                **({"chunks":plan,"chunk_count":len(plan),"chunk_size_max":CHUNK} if chunked else {}),
                "source_job_status": "succeeded",
                **({"source_attempt_id": attempt_id} if attempt_id is not None else {}),
            },
        }
        try:
            row = _upsert(config, payload)
            if chunked:_persist_chunks(config,artifact,Path(staged.name),plan)
        finally:
            Path(staged.name).unlink(missing_ok=True)
        # Independently GET the durable SQL row, reconstruct complete original
        # stored bytes, decompress/validate UTF-8 and rehash both representations.
        durable = _fetch_rows(config, "research_artifact_readbacks", {"artifact_id": f"eq.{artifact['artifact_id']}", "limit":"2"})
        if len(durable)!=1:raise RuntimeError("durable readback missing/duplicated")
        with tempfile.TemporaryDirectory(prefix="tr-sql-byte-parity-") as td:
            if chunked:
                _verify_chunks(config,durable[0],artifact,Path(td)/"durable-bytes")
                row=_update_one(config,'research_artifact_readbacks','artifact_id',artifact['artifact_id'],{'verified_sha256':True,'metadata_json':{**durable[0]['metadata_json'],'durable_chunked_sql_verified':True}})
                final=_fetch_rows(config,'research_artifact_readbacks',{'artifact_id':f"eq.{artifact['artifact_id']}",'select':'readback_id,artifact_id,size_bytes,sha256,verified_sha256,metadata_json','limit':'2'})
                if len(final)!=1 or final[0]['verified_sha256'] is not True or final[0]['sha256']!=actual_sha or final[0]['size_bytes']!=size or final[0]['metadata_json'].get('durable_chunked_sql_verified') is not True:raise RuntimeError('terminal durable chunked readback verification missing')
            else:verify_sql(durable[0], artifact, Path(td)/"durable-bytes")
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
