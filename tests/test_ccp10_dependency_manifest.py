from unittest.mock import patch

import pytest

from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.dependency_manifest import attach_dependency_manifest, resolve_dependency


def test_market_data_dependency_preserves_integrity_metadata() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    dep = resolve_dependency(config, {
        "type": "market_data",
        "object_path": "1m/SPY/2025.parquet",
        "object_size_bytes": 9736581,
        "sha256": "ABCDEF",
        "local_relative_path": "market_cache/MARKET_CACHE_V1/1m/SPY/2025.parquet",
    })
    assert dep.input_type == "market_data"
    assert dep.sha256 == "abcdef"
    assert dep.object_size_bytes == 9736581


def test_upstream_artifact_dependency_uses_recorded_checksum() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    artifact = {
        "artifact_id": "artifact-1",
        "bucket_name": "trading-research-market-data",
        "object_path": "artifacts/job/attempt/context_enriched.parquet",
        "size_bytes": 1234,
        "sha256": "feedbeef",
    }
    with patch("cloud_compute.dependency_manifest.fetch_artifact", return_value=artifact):
        dep = resolve_dependency(config, {
            "type": "upstream_artifact",
            "artifact_id": "artifact-1",
            "local_relative_path": "research_outputs/pmpd/post9n_batch1/context_enriched.parquet",
        })
    assert dep.input_type == "upstream_artifact"
    assert dep.source_artifact_id == "artifact-1"
    assert dep.sha256 == "feedbeef"


def test_dependency_rejects_unsafe_target_path() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    with pytest.raises(ValueError, match="unsafe local_relative_path"):
        resolve_dependency(config, {
            "type": "market_data",
            "object_path": "1m/SPY/2025.parquet",
            "local_relative_path": "../escape.parquet",
        })


def test_attach_manifest_creates_job_inputs() -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    with patch("cloud_compute.dependency_manifest.create_job_input", return_value={"input_id": "input-1"}) as create_input:
        rows = attach_dependency_manifest(
            config,
            job_id="job-1",
            dataset_version="DATASET-1",
            dependencies=[{
                "type": "market_data",
                "object_path": "1m/SPY/2025.parquet",
                "object_size_bytes": 9736581,
                "sha256": "aebd",
                "local_relative_path": "market_cache/MARKET_CACHE_V1/1m/SPY/2025.parquet",
            }],
        )
    assert rows == [{"input_id": "input-1"}]
    payload = create_input.call_args.args[1]
    assert payload["job_id"] == "job-1"
    assert payload["required"] is True
    assert payload["metadata_json"]["dependency_manifest_v1"] is True
