# Autonomous governed dispatch

Cloud Compute can now use a dedicated GitHub control branch as an execution trigger channel.

Normal flow:

1. Create or verify the governed `research_jobs` row in Supabase.
2. Write a small JSON request under `.github/dispatch-requests/` on the control branch.
3. GitHub receives the resulting push event and starts the autonomous dispatcher workflow.
4. The workflow validates job identity, queued state, executor, spend flag, and exact Git SHA against Supabase.
5. It checks out and verifies the exact governed SHA.
6. `cloud_compute.autonomous_loop` claims and executes the exact job.
7. Existing attempt, log, input, artifact, checksum, and provenance controls remain in force.

The request file is only an execution trigger. Supabase remains the authorization/control-plane source of truth.

This design removes the manual GitHub Actions `workflow_dispatch` click without introducing another paid executor. The existing manual dispatcher and Local Windows fallback remain available for rollback and incident recovery.

Cost policy remains `ZERO_INCREMENTAL_COST_FIRST` and `NO_INCREMENTAL_SPEND_WITHOUT_EXPLICIT_APPROVAL`. Cloud Run remains separate and requires explicit approval.

Research interpretation and model governance remain in the owning research project; Cloud Compute only handles execution infrastructure.
