# CCP-12 — Cloud / Local Operating Model

Status: ACTIVE
Operating model version: CCP12-1.0
Project: Trading Research Cloud Compute Platform (`CLOUD_COMPUTE`)

## Purpose

This operating model defines how TradingResearch workloads are executed after CCP-11 certification. The goal is to make cloud execution the routine path while preserving local Windows execution for development, debugging, controlled fallback, and archival workflows.

The operating model does not change research hypotheses, frozen strategy definitions, evidence classifications, or project ownership. Research logic remains owned by its research lane; the cloud platform owns execution, dependency materialization, persistence, reliability, and cost controls.

## Executor order

The governed executor order is:

1. `github_actions` — primary executor.
2. `cloud_run` — secondary overflow/scale executor, eligible only after explicit spend approval.
3. `local_windows` — tertiary fallback and development/debug executor.

The cost policy is `NO_INCREMENTAL_SPEND_WITHOUT_EXPLICIT_APPROVAL` and `ZERO_INCREMENTAL_COST_FIRST`.

Cloud Run must remain fail-closed unless `cloud_run_spend_approved=true`. If GitHub Actions is unavailable and Cloud Run is not explicitly approved, route to local Windows rather than incur spend.

## Standard research flow

Routine governed research should follow this path:

1. Code is versioned in GitHub at an exact Git SHA.
2. Required data dependencies are declared in the job input manifest.
3. Canonical inputs are materialized from governed object storage with exact size and SHA-256 verification.
4. A `research_jobs` control-plane record is created in Supabase.
5. GitHub Actions claims the exact eligible job atomically.
6. The shared `research_runner` executes the same research module used locally.
7. Every declared output file is validated and persisted to governed object storage.
8. Artifact rows, checksums, logs, attempts, timestamps, and executor provenance are written to Supabase.
9. Research interpretation remains in the owning research thread/project.

## When cloud execution is the default

Use GitHub Actions by default when all of the following are true:

- the research code is committed and has an exact Git SHA;
- all required dependencies are cloud-resident or materializable through a governed manifest;
- the workload fits standard GitHub-hosted runner limits;
- the repository remains public under the current zero-spend policy;
- no interactive desktop-only dependency is required.

## When local Windows is appropriate

Use local Windows intentionally for:

- rapid development before code is ready to commit;
- debugging environment-specific failures;
- workflows that require local-only files not yet promoted into governed storage;
- recovery when GitHub Actions is unavailable and Cloud Run has not been explicitly approved;
- archival/export operations that intentionally target local storage;
- one-off diagnostics where cloud setup would add more risk than value.

Local execution is not considered a governance bypass. The same Git SHA, dataset version, job ID when applicable, evidence rules, and artifact standards should be preserved.

## Cloud Run policy

Cloud Run is not a silent automatic fallback.

Before Cloud Run can execute a job:

- `cloud_run_available` must be true;
- `cloud_run_spend_approved` must be true;
- the approval must be explicit and current;
- the job must preserve the same Git SHA, inputs, runner contract, and artifact rules.

If any of those conditions are false, Cloud Run is ineligible.

## Job reliability policy

### Atomic claims

A governed job may be claimed by at most one worker attempt at a time. CCP-11 live certification proved an eight-way concurrent exact-job race produced one winner and seven null claims.

### Stale jobs

A running job is not recycled merely because it is old.

Recovery is fail-closed:

- if executor liveness is confirmed active: leave the job alone;
- if executor liveness is unknown: leave the job alone;
- if the executor is confirmed inactive and governed retry capacity remains: requeue;
- if the executor is confirmed inactive and no governed retry remains: quarantine/fail for review.

### Retry limits

Autonomous retry is bounded by the job's retry policy and hard platform limits. Retries must not change the Git SHA or silently retune research logic.

## Artifact policy

Every declared output is part of the research evidence package.

The worker must:

- validate that each declared path stays within `TR_WORK_ROOT`;
- fail if a declared file is missing;
- persist all declared output files, not only the primary summary;
- identify exactly one primary artifact when the runner declares one;
- compute and persist SHA-256 and size for every artifact;
- preserve object path, attempt ID, job ID, and runner-relative path provenance.

For deterministic workloads, repeated runs with the same Git SHA and canonical inputs should be compared by artifact checksum. CCP-11 certified byte-for-byte equality across all six outputs of the representative real research workload.

## Dependency policy

Inputs must be explicit and reproducible.

Supported dependency patterns include:

- `market_data` — canonical market-data objects;
- `upstream_artifact` — governed output from a prior research/import job.

Each required dependency should include object path, expected size, SHA-256, bucket, local relative path, and source artifact linkage where applicable.

Missing or mismatched required inputs are execution failures, not reasons to silently fall back to another dataset.

## Secrets and credentials

Secrets must remain server-side or local to the execution environment.

- Never place Supabase service secrets in source control.
- Never expose service-role/server secrets to the Vercel browser bundle.
- GitHub Actions uses repository secrets for Supabase access.
- Local PowerShell may use session-scoped environment variables.
- Credentials accidentally exposed in chat/logs must be rotated before reuse.

## Cost control

The platform's standing rule is zero incremental spend unless the user explicitly approves otherwise.

Operational checks include:

- repository visibility remains public for the primary standard GitHub-hosted runner path;
- Cloud Run assignment count remains zero unless explicitly approved;
- Cloud Run spend approvals remain zero unless explicitly approved;
- the web UI exposes operational compute telemetry and cost guard status;
- control-plane runtime telemetry is not labeled as provider billing data.

## Research-lane onboarding checklist

A research lane is cloud-ready when:

1. its runner job is registered;
2. its logic is committed and frozen for the intended run;
3. all required file dependencies are declared;
4. canonical dependencies are available in governed storage;
5. local relative paths are deterministic;
6. outputs are declared by the runner result;
7. the job can run from a clean cloud workspace;
8. artifacts and logs persist successfully;
9. repeated execution is reproducible to the level required by that workload;
10. lane-specific research interpretation remains outside the infrastructure thread.

## Normal operator actions

For routine work, the user should not need to run manual PowerShell commands. The target workflow is submission through the web/control plane followed by remote execution and persisted evidence.

Manual local commands should be reserved for development, explicit fallback, or diagnostics.

## Incident playbook

If a cloud job fails:

1. inspect the control-plane job, attempt, and logs;
2. determine whether failure is code, dependency, persistence, executor, or infrastructure related;
3. do not alter research rules simply to make the cloud run pass;
4. use governed retry only when allowed;
5. if executor state is uncertain, do not recycle the job until liveness is known;
6. if remote execution is unavailable and Cloud Run is not approved, use local Windows fallback;
7. retain failed attempt evidence.

## Governance boundaries

The Cloud Compute Platform may change infrastructure behavior, but it must not independently change:

- PMPD or other strategy hypotheses;
- frozen model thresholds;
- research grades or dispositions;
- evidence classifications;
- production authorization.

Those decisions remain with the owning research project.

## CCP-12 closeout criteria

CCP-12 can be marked complete when:

- this operating model is versioned and certified;
- executor selection matches the documented policy;
- the standard cloud submission path and local fallback path are documented and usable;
- the incident/recovery playbook is documented;
- zero-spend guardrails are explicit;
- research-lane onboarding requirements are explicit;
- project status reflects the mature operating model rather than an implementation phase.
