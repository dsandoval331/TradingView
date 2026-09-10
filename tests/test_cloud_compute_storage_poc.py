from pathlib import Path

from cloud_compute.storage_poc import _headers, _storage_url, run_poc


def test_storage_url_quotes_object_path() -> None:
    url = _storage_url(
        "https://example.supabase.co/",
        "object/authenticated",
        "private bucket",
        "1m/SPY/2025 sample.parquet",
    )
    assert url == (
        "https://example.supabase.co/storage/v1/object/authenticated/"
        "private%20bucket/1m/SPY/2025%20sample.parquet"
    )


def test_modern_secret_key_is_not_sent_as_bearer_jwt() -> None:
    headers = _headers("sb_secret_example_key", content_type="application/octet-stream")
    assert headers["apikey"] == "sb_secret_example_key"
    assert "Authorization" not in headers
    assert headers["Content-Type"] == "application/octet-stream"


def test_legacy_service_role_key_keeps_bearer_header() -> None:
    headers = _headers("eyJlegacy.jwt.value")
    assert headers["apikey"] == "eyJlegacy.jwt.value"
    assert headers["Authorization"] == "Bearer eyJlegacy.jwt.value"


def test_dry_run_hashes_selected_files_without_credentials(tmp_path: Path) -> None:
    cache = tmp_path / "MARKET_CACHE_V1"
    target = cache / "1m" / "SPY" / "2025.parquet"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"parquet-test-payload")
    output = tmp_path / "poc.json"

    record = run_poc(
        cache,
        ["1m/SPY/2025.parquet"],
        project_url=None,
        secret_key=None,
        bucket="trading-research-market-data",
        output=output,
        dry_run=True,
        allow_existing=False,
    )

    assert record["status"] == "READY"
    assert record["objects"][0]["status"] == "READY"
    assert record["objects"][0]["size_bytes"] == len(b"parquet-test-payload")
    assert len(record["objects"][0]["local_sha256"]) == 64
    assert output.is_file()
