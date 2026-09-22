from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cloud_compute.control_plane import (
    ControlPlaneConfig,
    create_job_input,
    fetch_artifact,
)


@dataclass(frozen=True)
class ResolvedDependency:
    input_type: str
    object_path: str
    object_size_bytes: int | None
    sha256: str | None
    local_relative_path: str
    bucket_name: str
    source_artifact_id: str | None = None


def _require_local_path(spec: dict[str, Any]) -> str:
    value = str(spec.get("local_relative_path") or "").strip().replace("\\", "/")
    if not value:
        raise ValueError("dependency requires local_relative_path")
    if value.startswith("/") or value.startswith("../") or "/../" in value:
        raise ValueError(f"unsafe local_relative_path: {value}")
    return value


def resolve_dependency(
    config: ControlPlaneConfig,
    spec: dict[str, Any],
    *,
    default_bucket: str = "trading-research-market-data",
) -> ResolvedDependency:
    kind = str(spec.get("type") or "").strip().lower()
    local_path = _require_local_path(spec)

    if kind == "market_data":
        object_path = str(spec.get("object_path") or "").strip().replace("\\", "/").lstrip("/")
        if not object_path:
            raise ValueError("market_data dependency requires object_path")
        expected_sha = str(spec.get("sha256") or "").strip().lower() or None
        expected_size = spec.get("object_size_bytes")
        if expected_size is not None:
            expected_size = int(expected_size)
        return ResolvedDependency(
            input_type="market_data",
            object_path=object_path,
            object_size_bytes=expected_size,
            sha256=expected_sha,
            local_relative_path=local_path,
            bucket_name=str(spec.get("bucket_name") or default_bucket),
        )

    if kind == "upstream_artifact":
        artifact_id = str(spec.get("artifact_id") or "").strip()
        if not artifact_id:
            raise ValueError("upstream_artifact dependency requires artifact_id")
        artifact = fetch_artifact(config, artifact_id)
        if artifact is None:
            raise ValueError(f"upstream artifact not found: {artifact_id}")
        object_path = str(artifact.get("object_path") or "").strip()
        sha256 = str(artifact.get("sha256") or "").strip().lower()
        size = artifact.get("size_bytes")
        if not object_path or not sha256 or size is None:
            raise ValueError(f"upstream artifact is missing integrity metadata: {artifact_id}")
        return ResolvedDependency(
            input_type="upstream_artifact",
            object_path=object_path,
            object_size_bytes=int(size),
            sha256=sha256,
            local_relative_path=local_path,
            bucket_name=str(artifact.get("bucket_name") or default_bucket),
            source_artifact_id=artifact_id,
        )

    raise ValueError(f"unsupported dependency type: {kind}")


def attach_dependency_manifest(
    config: ControlPlaneConfig,
    *,
    job_id: str,
    dataset_version: str | None,
    dependencies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    for spec in dependencies:
        dep = resolve_dependency(config, spec)
        metadata = {
            "bucket_name": dep.bucket_name,
            "local_relative_path": dep.local_relative_path,
            "dependency_manifest_v1": True,
        }
        if dep.source_artifact_id:
            metadata["source_artifact_id"] = dep.source_artifact_id
        created.append(create_job_input(config, {
            "job_id": job_id,
            "input_type": dep.input_type,
            "dataset_version": dataset_version,
            "object_path": dep.object_path,
            "object_size_bytes": dep.object_size_bytes,
            "sha256": dep.sha256,
            "required": bool(spec.get("required", True)),
            "metadata_json": metadata,
        }))
    return created
