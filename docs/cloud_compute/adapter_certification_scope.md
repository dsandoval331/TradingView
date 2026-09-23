# Research revision adapter certification acceptance criteria

PASS requires:

1. Existing CCP5-CCP9 regression tests pass unchanged.
2. Queue watcher regression tests pass unchanged during the isolated adapter phase.
3. Adapter records distinct research and infrastructure SHAs.
4. Non-full research SHAs are rejected.
5. Historical runner failures are surfaced and cannot be reported as success.
6. No database migration, Cloud Run execution, or research methodology change is introduced.

Production dispatcher/worker wiring is a second gated commit after these criteria pass.
