from __future__ import annotations

import argparse
import json
import os

from cloud_compute.control_plane import ControlPlaneConfig, fetch_queued_jobs


def eligible_jobs(config: ControlPlaneConfig, *, limit: int = 10) -> list[dict]:
    rows = fetch_queued_jobs(config, limit=max(limit * 4, 20))
    out = []
    for row in rows:
        if row.get("preferred_executor") != "github_actions":
            continue
        if bool(row.get("cloud_run_spend_approved")):
            continue
        sha = str(row.get("git_sha") or "")
        job_id = str(row.get("job_id") or "")
        if len(sha) != 40 or len(job_id) != 36:
            continue
        out.append({"job_id": job_id, "git_sha": sha, "target_ref": sha})
        if len(out) >= limit:
            break
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Select governed queued jobs eligible for zero-cost GitHub execution")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    jobs = eligible_jobs(ControlPlaneConfig(url, key), limit=args.limit)
    payload = json.dumps(jobs, separators=(",", ":"))
    print(payload)
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"jobs={payload}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
