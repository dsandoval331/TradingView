from __future__ import annotations

import argparse

from research_runner import runner


def run_once(job_id: str | None = None, project: str | None = None) -> int:
    """Execute exactly one eligible research job through the common runner contract."""
    if job_id:
        return runner.run_id(job_id)
    return runner.run_next(project)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local fallback worker for TradingResearch hybrid execution"
    )
    parser.add_argument("--job-id")
    parser.add_argument("--project", choices=["ccp", "ccp4", "pmpd"])
    args = parser.parse_args()
    if args.job_id and args.project:
        parser.error("use either --job-id or --project, not both")
    return run_once(job_id=args.job_id, project=args.project)


if __name__ == "__main__":
    raise SystemExit(main())
