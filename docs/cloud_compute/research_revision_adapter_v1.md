# Governed Research Revision Adapter v1

The control-plane infrastructure revision and governed research revision are distinct provenance identities.

- `research_jobs.git_sha` is the exact governed research SHA.
- The Actions checkout SHA is the certified infrastructure SHA.
- Current CCP contract tests execute against the infrastructure checkout.
- Historical research is materialized into a detached git worktree at the exact governed research SHA.
- The adapter verifies the research worktree HEAD before execution.
- Historical `research_runner.runner.run_id` executes in a child process rooted at that verified worktree.
- Attempt/artifact provenance must record both SHAs and `exact_research_sha_verified=true`.
- This adapter must not alter historical research modules, inputs, labels, thresholds, or methodology.
- Atomic claim and zero-incremental-cost executor policy remain control-plane responsibilities.
