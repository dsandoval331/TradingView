# CCP-5 — Supabase Job / Control Plane

## Objective

Create a durable, executor-neutral control plane so research jobs can be queued, assigned, executed, retried, and audited without changing research methodology.

## Tables

- `research_jobs` — authoritative job identity, requested runner job, project/phase, executor assignment, Git SHA, dataset version, status, cost gate, timestamps, and parameters.
- `research_job_attempts` — one row per execution attempt, including executor, external execution ID, status, Git SHA, timing, exit code, and failure metadata.
- `research_job_inputs` — immutable input object identity including object path, dataset version, size, and SHA-256.

The existing `research_runs` table remains the research-result/run record. `research_jobs.research_run_id` can link orchestration to a completed research run without overloading either table.

## Executor policy

Default priority remains:

1. `github_actions`
2. `cloud_run`
3. `local_windows`

Cloud Run remains ineligible unless `cloud_run_spend_approved = true` for the job/operating window. Executor choice is infrastructure metadata and must not change the job's Git SHA, dataset identity, configuration, or evidence rules.

## Security posture

The CCP-5 tables have RLS enabled and intentionally have no client-facing policies during the initial service-side phase. Elevated server-side workers may access them through a private Supabase secret/service role. Browser clients must not receive that credential. Web-app access will be introduced later through deliberately scoped server-side APIs or explicit RLS policies.

## Initial API contract

`cloud_compute.control_plane` provides a small REST client for:

- creating a job;
- fetching queued/local-pending jobs in deterministic priority order;
- updating job state;
- creating execution-attempt records.

The client preserves the CCP-2 authentication fix: modern `sb_secret_*` keys are sent as `apikey` and are not incorrectly treated as JWT Bearer tokens.

## Status model

Job statuses:

`queued -> assigned -> running -> succeeded|failed`

Additional controlled states:

- `local_pending` — remote capacity unavailable; eligible for local fallback.
- `blocked` — cannot execute because a policy/dependency gate is unsatisfied.
- `cancelled` — intentionally stopped.

Attempt statuses:

`queued -> running -> succeeded|failed|cancelled`

## Current certification gates

1. Database schema exists with RLS and indexes.
2. Security/performance advisors are reviewed after DDL.
3. Client unit tests certify auth headers and deterministic REST semantics.
4. A real service-side CCP-5 proof job is inserted, assigned, attempted, and completed in Supabase.
5. Next step: connect GitHub Actions to consume/complete a real control-plane job without exposing long-lived secrets in repository code.
