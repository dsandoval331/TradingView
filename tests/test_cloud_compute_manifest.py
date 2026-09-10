from __future__ import annotations

import hashlib
from pathlib import Path

from cloud_compute.manifest import build_manifest


def test_build_manifest_is_sorted_and_hashes_files(tmp_path: Path) -> None:
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "two.txt").write_text("two", encoding="utf-8")
    (tmp_path / "one.txt").write_text("one", encoding="utf-8")

    manifest = build_manifest(tmp_path)

    assert manifest["manifest_version"] == 1
    assert manifest["file_count"] == 2
    assert manifest["total_bytes"] == 6
    assert [item["path"] for item in manifest["files"]] == ["b/two.txt", "one.txt"]
    assert manifest["files"][0]["sha256"] == hashlib.sha256(b"two").hexdigest()
    assert manifest["files"][1]["sha256"] == hashlib.sha256(b"one").hexdigest()
