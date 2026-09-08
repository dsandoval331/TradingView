from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the PMS historical snapshot generator twice and prove byte-for-byte reproducibility."
    )
    p.add_argument("--trade-date", required=True)
    p.add_argument("--snapshot-code", choices=["SCAN_A", "SCAN_B", "BOTH"], default="BOTH")
    p.add_argument("--symbols", nargs="+", default=None)
    return p.parse_args()


def run_once(args: argparse.Namespace, output_root: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "tr_platform.downloader.generate_pms_historical_snapshot",
        "--trade-date",
        args.trade_date,
        "--snapshot-code",
        args.snapshot_code,
        "--output-root",
        str(output_root),
    ]
    if args.symbols:
        cmd.extend(["--symbols", *args.symbols])
    subprocess.run(cmd, check=True)


def file_manifest(root: Path) -> dict[str, str]:
    files = sorted(p for p in root.rglob("*") if p.is_file())
    return {p.relative_to(root).as_posix(): sha256_file(p) for p in files}


def main() -> None:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="pms_det_a_") as a, tempfile.TemporaryDirectory(prefix="pms_det_b_") as b:
        a_root = Path(a)
        b_root = Path(b)

        print("=== PMS DETERMINISM RUN A ===")
        run_once(args, a_root)

        print("=== PMS DETERMINISM RUN B ===")
        run_once(args, b_root)

        ma = file_manifest(a_root)
        mb = file_manifest(b_root)

        names = sorted(set(ma) | set(mb))
        mismatches = []
        for name in names:
            if ma.get(name) != mb.get(name):
                mismatches.append({
                    "file": name,
                    "run_a_sha256": ma.get(name),
                    "run_b_sha256": mb.get(name),
                })

        result = {
            "trade_date": args.trade_date,
            "snapshot_code": args.snapshot_code,
            "file_count_run_a": len(ma),
            "file_count_run_b": len(mb),
            "deterministic": len(mismatches) == 0 and ma.keys() == mb.keys(),
            "mismatches": mismatches,
            "hashes": ma if not mismatches else None,
        }

        print()
        print("=== PMS DETERMINISM RESULT ===")
        print(json.dumps(result, indent=2))

        if not result["deterministic"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
