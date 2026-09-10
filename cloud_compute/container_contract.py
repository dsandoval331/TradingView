from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def inspect_contract(code_root: Path | None = None) -> dict:
    root = (code_root or Path(__file__).resolve().parents[1]).resolve()
    work_root = Path(os.environ.get("TR_WORK_ROOT", str(root))).expanduser().resolve()
    git_sha = os.environ.get("TR_GIT_SHA")
    return {
        "code_root": str(root),
        "work_root": str(work_root),
        "git_sha": git_sha,
        "requirements_present": (root / "requirements.txt").is_file(),
        "runner_present": (root / "research_runner" / "runner.py").is_file(),
        "workspace_separated": work_root != root,
        "provenance_injected": bool(git_sha and git_sha != "unknown"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect CCP-3 runtime contract")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    record = inspect_contract()
    if args.json:
        print(json.dumps(record, indent=2))
    else:
        for key, value in record.items():
            print(f"{key.upper()}={value}")
    required = record["requirements_present"] and record["runner_present"] and record["workspace_separated"] and record["provenance_injected"]
    return 0 if required else 1


if __name__ == "__main__":
    raise SystemExit(main())
