from pathlib import Path
from unittest.mock import patch

import pytest

from cloud_compute.control_plane import ControlPlaneConfig
from cloud_compute.input_materializer import materialize_job_inputs


def test_materializes_market_data_with_checksum_and_size(tmp_path: Path) -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    payload = b"parquet-bytes"
    import hashlib
    digest = hashlib.sha256(payload).hexdigest()
    rows = [{
        "input_id": "input-1",
        "input_type": "market_data",
        "object_path": "1m/SPY/2025.parquet",
        "object_size_bytes": len(payload),
        "sha256": digest,
        "required": True,
        "metadata_json": {"bucket_name": "trading-research-market-data"},
    }]

    def fake_download(project_url, secret_key, bucket, object_path, destination):
        assert bucket == "trading-research-market-data"
        assert object_path == "1m/SPY/2025.parquet"
        destination.write_bytes(payload)

    with (
        patch("cloud_compute.input_materializer.fetch_job_inputs", return_value=rows),
        patch("cloud_compute.input_materializer._download_object", side_effect=fake_download),
    ):
        result = materialize_job_inputs(config, job_id="job-1", work_root=tmp_path)

    assert len(result) == 1
    item = result[0]
    assert item.sha256 == digest
    assert item.size_bytes == len(payload)
    assert item.local_path == tmp_path / "market_cache/MARKET_CACHE_V1/1m/SPY/2025.parquet"
    assert item.local_path.read_bytes() == payload


def test_checksum_mismatch_fails_closed_and_deletes_file(tmp_path: Path) -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    rows = [{
        "input_id": "input-2",
        "input_type": "market_data",
        "object_path": "1m/AAPL/2025.parquet",
        "sha256": "0" * 64,
        "required": True,
        "metadata_json": {},
    }]

    def fake_download(project_url, secret_key, bucket, object_path, destination):
        destination.write_bytes(b"wrong")

    with (
        patch("cloud_compute.input_materializer.fetch_job_inputs", return_value=rows),
        patch("cloud_compute.input_materializer._download_object", side_effect=fake_download),
    ):
        with pytest.raises(RuntimeError, match="checksum mismatch"):
            materialize_job_inputs(config, job_id="job-2", work_root=tmp_path)

    assert not (tmp_path / "market_cache/MARKET_CACHE_V1/1m/AAPL/2025.parquet").exists()


def test_explicit_local_path_cannot_escape_work_root(tmp_path: Path) -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    rows = [{
        "input_id": "input-3",
        "input_type": "file",
        "object_path": "anything.bin",
        "required": True,
        "metadata_json": {"local_relative_path": "../escape.bin"},
    }]
    with patch("cloud_compute.input_materializer.fetch_job_inputs", return_value=rows):
        with pytest.raises(RuntimeError, match="escapes work root"):
            materialize_job_inputs(config, job_id="job-3", work_root=tmp_path)


def test_optional_missing_input_does_not_fail_job(tmp_path: Path) -> None:
    config = ControlPlaneConfig("https://example.supabase.co", "sb_secret_example")
    rows = [{
        "input_id": "input-4",
        "input_type": "market_data",
        "object_path": "1m/MISSING/2025.parquet",
        "required": False,
        "metadata_json": {},
    }]
    with (
        patch("cloud_compute.input_materializer.fetch_job_inputs", return_value=rows),
        patch("cloud_compute.input_materializer._download_object", side_effect=RuntimeError("not found")),
    ):
        assert materialize_job_inputs(config, job_id="job-4", work_root=tmp_path) == []
