# Queue Resilience v1

Scope: infrastructure/control-plane recovery only. Research methodology, datasets, thresholds, runner semantics, and frozen research revisions are out of scope.

## Safety invariants

1. A wake-up is only a notification to the authoritative GitHub queue watcher; it never identifies a research job to execute.
2. Exact governed research SHA remains mandatory at dispatch and atomic claim.
3. Retrying a wake-up does not requeue or mutate a research job.
4. A stale `running` job is detected and escalated first; it is not automatically returned to `queued` until ownership/attempt state proves recovery is safe.
5. Cloud Run remains unavailable unless incremental spend is explicitly approved.

## Initial policy

- `pending` wake-up older than 2 minutes: retry candidate.
- `requested` wake-up without acknowledgement after 5 minutes: retry candidate.
- `failed` wake-up older than 2 minutes: retry candidate.
- Maximum automatic wake-up attempts: 5.
- `running` job older than 30 minutes: stale-running candidate for ownership reconciliation, not automatic requeue.

These thresholds are operational defaults and do not alter research semantics.

## Certification plan

1. Reconcile historical/stale wake-up events through a dedicated infrastructure reconciler.
2. Prove concurrent/repeated wake-ups cannot create more than one successful atomic claim for one job.
3. Inject dispatch and worker failures and verify observable retry/exhaustion states.
4. Add queue/recovery telemetry and freeze the operating model after production certification.
