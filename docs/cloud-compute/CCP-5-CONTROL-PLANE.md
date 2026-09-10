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

## API contract

`cloud_compute.control_plane` provides the executor-neutral REST client for creating jobs, fetching queued/local-pending jobs in deterministic priority order, updating job state, and creating execution-attempt records.

`cloud_compute.control_plane_worker` adds the worker lifecycle: select an eligible queued job, mark it running, create an attempt, call the common `research_runner run-id` contract, and report success or failure back to Supabase.

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

## Certification

CCP-5 is certified.

1. Database schema exists with RLS and supporting indexes.
2. Security/performance advisors were reviewed after DDL.
3. Control-plane client tests passed in GitHub Actions.
4. A real service-side lifecycle proof was created and completed in Supabase.
5. A real GitHub Actions worker consumed a queued Supabase job, created an attempt, executed `CCP3-PARITY-FIXTURE`, and reported success back to Supabase.
6. Live certification GitHub Actions run: `34425290629`.
7. Certified Supabase job: `638f33a0-4012-4119-aa72-68ffa08d5390`.
8. Certified attempt: `64ec8ca2-cd2e-4263-b4a8-ffc2611bb60c`.
9. Executor: `github_actions`; exit code: `0`; no error recorded.

## Disposition

**COMPLETE — advance to CCP-6 Artifact & Log Management.**
