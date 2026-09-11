# TradingResearch Cloud Compute — Operator Quickstart

This is the day-to-day operating guide for the mature Cloud Compute Platform.

## Normal operation: web/cloud first

For routine research execution:

1. Use the TradingResearch web/control interface to submit an eligible governed job.
2. The job is created in Supabase with an exact Git SHA, dataset version, parameters, and declared inputs.
3. GitHub Actions is the normal primary executor.
4. Required inputs are materialized from governed storage and checksum-verified.
5. The shared `research_runner` executes the requested job.
6. Logs, attempts, and all declared artifacts are persisted automatically.
7. Review the resulting evidence in the owning research project/thread.

Routine operation should not require a local `git pull` or manual PowerShell execution loop.

## What to check when a job does not finish

Check, in order:

1. control-plane job status;
2. latest attempt status and external execution ID;
3. materialized-input log entries;
4. runner stdout/stderr logs;
5. persisted artifact count and primary artifact;
6. GitHub Actions run status.

Do not recycle a stale job while the external executor may still be active. Unknown liveness is a fail-closed state.

## Local Windows fallback

Local Windows is the fallback when GitHub Actions is unavailable and Cloud Run is not explicitly spend-approved, and is also appropriate for development/debugging.

From the repository root with the Python environment activated:

```powershell
python -m research_runner.runner status
python -m research_runner.runner run-id <RUNNER_JOB_ID>
```

For a governed control-plane job that has been intentionally routed to local execution:

```powershell
python -m cloud_compute.local_worker --job-id <JOB_ID>
```

Local execution must use the intended Git SHA and canonical inputs. Do not substitute local data merely to make a failed cloud job pass.

## Cloud Run

Cloud Run is not a default fallback. It is used only after explicit spend approval. Without approval, the routing order effectively becomes:

```text
GitHub Actions -> Local Windows
```

With explicit Cloud Run approval and technical availability:

```text
GitHub Actions -> Cloud Run -> Local Windows
```

## Cost rule

Standing rule:

```text
NO_INCREMENTAL_SPEND_WITHOUT_EXPLICIT_APPROVAL
ZERO_INCREMENTAL_COST_FIRST
```

If repository visibility, provider limits, or account configuration changes in a way that could make the primary path billable, submission should fail closed until the cost implication is reviewed.

## Research boundary

Infrastructure can execute research, but it does not own the interpretation. Results, hypotheses, threshold changes, grades, dispositions, and production decisions remain in each research lane's dedicated project/thread.
