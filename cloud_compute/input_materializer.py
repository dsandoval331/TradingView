from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cloud_compute.control_plane import ControlPlaneConfig, fetch_job_inputs
from cloud_compute.manifest import sha256_file
from cloud_compute.storage_poc import DEFAULT_BUCKET, _download_object


@dataclass(frozen=True)
class MaterializedInput:
    input_id: str
    object_path: str
    local_path: Path
    size_bytes: int
    sha256: str


def _safe_target(work_root: Path, input_row: dict[str, Any]) -> Path:
    metadata = input_row.get('metadata_json') or {}
    rel = metadata.get('local_relative_path')
    if not rel:
        input_type = str(input_row.get('input_type') or '').strip().lower()
        object_path = str(input_row.get('object_path') or '').replace('\\', '/').lstrip('/')
        if input_type == 'market_data':
            rel = f'market_cache/MARKET_CACHE_V1/{object_path}'
        else:
            rel = f'job_inputs/{object_path}'
    root = work_root.resolve()
    target = (root / str(rel)).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f'input target escapes work root: {rel}') from exc
    return target


def materialize_job_inputs(
    config: ControlPlaneConfig,
    *,
    job_id: str,
    work_root: Path,
    default_bucket: str = DEFAULT_BUCKET,
) -> list[MaterializedInput]:
    rows = fetch_job_inputs(config, job_id)
    results: list[MaterializedInput] = []
    for row in rows:
        object_path = str(row.get('object_path') or '').strip()
        if not object_path:
            if bool(row.get('required', True)):
                raise RuntimeError('required job input is missing object_path')
            continue
        metadata = row.get('metadata_json') or {}
        bucket = str(metadata.get('bucket_name') or default_bucket)
        target = _safe_target(work_root, row)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            _download_object(config.supabase_url, config.secret_key, bucket, object_path, target)
        except Exception:
            if not bool(row.get('required', True)):
                continue
            raise

        size = target.stat().st_size
        digest = sha256_file(target)
        expected_size = row.get('object_size_bytes')
        expected_sha = row.get('sha256')
        if expected_size is not None and int(expected_size) != size:
            target.unlink(missing_ok=True)
            raise RuntimeError(f'input size mismatch for {object_path}: expected {expected_size}, got {size}')
        if expected_sha and str(expected_sha).lower() != digest.lower():
            target.unlink(missing_ok=True)
            raise RuntimeError(f'input checksum mismatch for {object_path}')

        results.append(MaterializedInput(
            input_id=str(row.get('input_id') or ''),
            object_path=object_path,
            local_path=target,
            size_bytes=size,
            sha256=digest,
        ))
    return results
