from __future__ import annotations

from pathlib import Path
import shutil

from tr_platform.common.manifest import (
    CachePartitionRecord,
    LocalManifest,
    sha256_file,
    utc_now_iso,
)


def main() -> None:
    root = Path("market_cache") / "MARKET_CACHE_V1" / "manifest_tests"
    root.mkdir(parents=True, exist_ok=True)

    manifest_path = root / "market_cache_manifest_test.parquet"
    fake_partition = root / "AAPL_2026.parquet"

    if manifest_path.exists():
        manifest_path.unlink()
    if fake_partition.exists():
        fake_partition.unlink()

    fake_partition.write_bytes(b"manifest smoke test")

    manifest = LocalManifest(manifest_path)

    record = CachePartitionRecord(
        symbol="aapl",
        year=2026,
        requested_start="2026-01-01",
        requested_end="2026-12-31",
        row_count=12345,
        download_status="DOWNLOADED",
        validation_status="PASS",
        download_attempts=1,
        last_download_at=utc_now_iso(),
        last_validated_at=utc_now_iso(),
        local_relative_path=str(fake_partition),
        file_size_bytes=fake_partition.stat().st_size,
        file_hash=sha256_file(fake_partition),
    )

    manifest.upsert(record)

    loaded = manifest.get("AAPL", 2026)
    assert loaded is not None
    assert loaded["symbol"] == "AAPL"
    assert loaded["download_status"] == "DOWNLOADED"
    assert loaded["validation_status"] == "PASS"

    assert manifest.is_complete(
        symbol="AAPL",
        year=2026,
        expected_path=fake_partition,
    )

    next_item = manifest.next_incomplete(
        symbols=["AAPL", "MSFT"],
        years=[2026],
        path_builder=lambda s, y: root / f"{s}_{y}.parquet",
    )

    assert next_item == ("MSFT", 2026)

    print("=== MANIFEST SMOKE TEST PASS ===")
    print(f"Manifest path: {manifest_path}")
    print(f"Rows: {len(manifest.load())}")
    print(f"AAPL 2026 complete: {manifest.is_complete('AAPL', 2026, fake_partition)}")
    print(f"Next incomplete: {next_item}")
    print(f"SHA256 length: {len(loaded['file_hash'])}")


if __name__ == "__main__":
    main()
