from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .research_dataset import run_full_universe_research_dataset


def main() -> None:
    p = argparse.ArgumentParser(description="Build PMPD V5 9H outcome research dataset")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--year", type=int, default=2025)
    p.add_argument("--output", default="pmpd_v5_9h_research_dataset_v1")
    p.add_argument("--skip-file-hash", action="store_true")
    args = p.parse_args()

    root = Path(args.repo_root).resolve()
    out = root / args.output
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    outputs, payload = run_full_universe_research_dataset(
        repo_root=root,
        year=args.year,
        verify_hash=not args.skip_file_hash,
    )

    for name in ["symbol_summary", "session_quality", "geometry", "events", "decision_research"]:
        outputs[name].to_csv(out / f"{name}.csv", index=False)
    (out / "run_fingerprint.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )

    archive = shutil.make_archive(str(out), "zip", root_dir=out)
    print("9H research dataset complete.")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"Package: {archive}")


if __name__ == "__main__":
    main()
