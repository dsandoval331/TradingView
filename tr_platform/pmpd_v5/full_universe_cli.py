from __future__ import annotations
import argparse, json, shutil
from pathlib import Path

from tr_platform.pmpd_v5.certification import run_full_universe_structural_baseline

def main():
    p = argparse.ArgumentParser(description="PMPD V5 Alpha 0.2 full-universe structural baseline")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--year", type=int, default=2025)
    p.add_argument("--output", default="pmpd_v5_alpha_0_2_full_universe")
    p.add_argument("--skip-file-hash", action="store_true")
    args = p.parse_args()

    root = Path(args.repo_root).resolve()
    out = root / args.output
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    summary, outputs, payload = run_full_universe_structural_baseline(
        repo_root=root, year=args.year, verify_hash=not args.skip_file_hash
    )

    summary.to_csv(out / "symbol_summary.csv", index=False)
    for name in ["coverage", "session_levels", "geometry", "events", "transitions", "decision_points"]:
        outputs[name].to_csv(out / f"{name}.csv", index=False)

    (out / "run_fingerprint.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )

    archive = shutil.make_archive(str(out), "zip", root_dir=out)
    print(f"Full-universe structural baseline complete.")
    print(f"Symbols: {payload['symbol_count']}")
    print(f"Events: {payload['total_events']}")
    print(f"Transitions: {payload['total_transitions']}")
    print(f"Decision points: {payload['total_decision_points']}")
    print(f"Package: {archive}")

if __name__ == "__main__":
    main()
