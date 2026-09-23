# Research revision adapter safety invariants

- Never execute an abbreviated or unresolved research revision.
- Verify detached worktree HEAD equals the governed 40-character research SHA.
- Never mutate the infrastructure checkout while materializing historical research.
- Execute historical research with the verified research root as cwd/PYTHONPATH.
- Treat non-zero child exit as failure.
- Persist research SHA and infrastructure SHA as separate provenance values.
- Do not use the adapter to bypass atomic claim, registered-input verification, or artifact persistence.
