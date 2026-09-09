from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path) -> dict:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Manifest root does not exist or is not a directory: {root}")

    files = []
    total_bytes = 0
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        size = path.stat().st_size
        total_bytes += size
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": size,
                "sha256": sha256_file(path),
            }
        )

    return {
        "manifest_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "root_name": root.name,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic file/hash manifest for a research dataset tree.")
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manifest = build_manifest(args.root)
    payload = json.dumps(manifest, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
