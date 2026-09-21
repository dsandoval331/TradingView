from pathlib import Path
from unittest.mock import patch

import pytest

from cloud_compute.promote_canonical_artifact import promote


def test_promote_hashes_uploads_downloads_and_verifies(tmp_path: Path) -> None:
    source = tmp_path / "context_enriched.parquet"
    source.write_bytes(b"canonical-upstream-artifact")

    def fake_download(project_url, secret_key, bucket, object_path, destination):
        destination.write_bytes(source.read_bytes())

    with (
        patch("cloud_compute.promote_canonical_artifact._upload_object", return_value="UPLOADED") as upload,
        patch("cloud_compute.promote_canonical_artifact._download_object", side_effect=fake_download) as download,
    ):
        record = promote(
            source,
            project_url="https://example.supabase.co",
            secret_key="sb_secret_example",
            object_path="upstream/pmpd/post9n_batch1/context_enriched.parquet",
        )

    assert record["parity"] is True
    assert record["size_bytes"] == len(b"canonical-upstream-artifact")
    assert len(record["sha256"]) == 64
    upload.assert_called_once()
    download.assert_called_once()


def test_promote_fails_if_source_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="canonical artifact not found"):
        promote(
            tmp_path / "missing.parquet",
            project_url="https://example.supabase.co",
            secret_key="sb_secret_example",
        )


def test_promote_fails_closed_on_download_parity_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "context_enriched.parquet"
    source.write_bytes(b"canonical")

    def fake_download(project_url, secret_key, bucket, object_path, destination):
        destination.write_bytes(b"corrupt")

    with (
        patch("cloud_compute.promote_canonical_artifact._upload_object", return_value="UPLOADED"),
        patch("cloud_compute.promote_canonical_artifact._download_object", side_effect=fake_download),
    ):
        with pytest.raises(RuntimeError, match="parity failed"):
            promote(
                source,
                project_url="https://example.supabase.co",
                secret_key="sb_secret_example",
            )
