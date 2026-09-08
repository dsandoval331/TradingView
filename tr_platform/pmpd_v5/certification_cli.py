from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from tr_platform.pmpd_v5.certification import (
    compare_package_fingerprints,
    write_certification_package,
)


def main() -> None:
    p = argparse.ArgumentParser(description="PMPD V5 Alpha 0.1 structural certification")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--year", type=int, default=2025)
    p.add_argument("--symbols", type=int, default=5)
    p.add_argument("--dates", type=int, default=10)
    p.add_argument("--output", default="pmpd_v5_alpha_certification")
    p.add_argument("--skip-file-hash", action="store_true")
    args = p.parse_args()

    root = Path(args.repo_root).resolve()
    out_base = root / args.output
    run1 = out_base / "run_1"
    run2 = out_base / "run_2"

    if out_base.exists():
        shutil.rmtree(out_base)

    print("Running structural certification pass 1...")
    write_certification_package(
        repo_root=root, output_dir=run1, year=args.year,
        symbol_count=args.symbols, dates_per_symbol=args.dates,
        verify_hash=not args.skip_file_hash,
    )

    print("Running structural certification pass 2...")
    write_certification_package(
        repo_root=root, output_dir=run2, year=args.year,
        symbol_count=args.symbols, dates_per_symbol=args.dates,
        verify_hash=not args.skip_file_hash,
    )

    issues = compare_package_fingerprints(
        run1 / "run_fingerprint.json", run2 / "run_fingerprint.json"
    )
    status = "PASS" if not issues else "FAIL"
    (out_base / "DETERMINISM_STATUS.txt").write_text(
        status + "\n" + ("\n".join(issues) if issues else "Exact structural fingerprints matched.\n"),
        encoding="utf-8",
    )

    archive = shutil.make_archive(str(out_base), "zip", root_dir=out_base)
    print(f"Determinism: {status}")
    print(f"Certification package: {archive}")
    if issues:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
