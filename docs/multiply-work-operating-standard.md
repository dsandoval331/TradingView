# MULtipLY ChatGPT Work Operating Standard

Status: CERTIFIED / ADOPTED
Canonical source thread: `Infra: Evaluating ChatGPT Work for MULtipLY project`
Certification closure: 2026-10-01

## Purpose

ChatGPT Work is adopted as a controlled operational-orchestration layer for MULtipLY. It does not replace canonical research threads, Supabase, GitHub, or governed execution.

## MWE

MWE means **MULtipLY Work Envelope**. An MWE is the durable contract around a substantial unit of operational work delegated to ChatGPT Work.

A canonical research thread establishes the research methodology, frozen contract, consequential decisions, and roadmap authority. Work executes substantial multi-step operational activity within that contract. Supabase persists authoritative control-plane state. GitHub remains authoritative for code/revision history. GitHub Actions remains the primary zero-incremental-cost deterministic execution path.

## Authority model

- **E0** — observational/read-only work: discovery, inspection, status, analysis, verification, and preparation that does not mutate durable state.
- **E1** — bounded operational mutation already authorized by the frozen contract: non-methodological integration fixes, governed execution/recovery, persistence, verification, and other reversible/controlled operational actions.
- **E2** — consequential action requiring explicit user authorization: research-methodology changes, crossing a protected outcome-blindness gate when not already authorized, paid compute, destructive or difficult-to-reverse actions, material scope changes, security-sensitive authorization, or comparable consequential decisions.

An MWE may not exceed its persisted authority ceiling. When additional authority is required, durable state must surface `USER ACTION REQUIRED` rather than silently continuing.

## Lifecycle

Canonical MWE lifecycle states are:

`DRAFT -> READY -> ACTIVE -> VERIFYING -> COMPLETE`

Exceptional states are:

- `BLOCKED_USER`
- `BLOCKED_EXTERNAL`
- `FAILED`
- `CANCELLED`

MWE status is authoritative for orchestration state. `research_jobs.status` remains authoritative for governed execution state. One must not be inferred solely from the other.

## Durable control plane

The production MWE layer is additive to the existing governed research control plane:

- `work_envelopes` — MWE identity, lifecycle, frozen contract, authority, escalation, cost policy, and handoff metadata.
- `work_envelope_research_jobs` — relationship between an MWE and one or more governed research jobs.
- `work_envelope_events` — orchestration/recovery/escalation audit events.

Existing `research_jobs`, attempts, inputs, logs, artifacts, artifact readbacks, and compute-provider state remain authoritative for their respective domains and are not duplicated into MWE.

Browser access is read-only. Governed-job visibility for the MWE UI uses a scoped authenticated read path rather than broad browser access to `research_jobs`.

## Compute and cost policy

`ZERO_INCREMENTAL_COST_FIRST` remains the default policy.

Executor order remains governed by the existing compute-provider control plane. GitHub Actions is the primary deterministic path. Cloud Run or other paid/overflow compute requires the applicable explicit spend authorization. MWE does not maintain a competing quota/spend model.

## Standard operating flow

1. Canonical thread establishes the objective, frozen contract, authority ceiling, cost policy, completion criteria, and receiving thread.
2. Create/persist an MWE before substantial Work execution when the task is suitable for Work orchestration.
3. Work discovers current durable state before acting; it does not assume ordinary chat work continued in the background.
4. Work proceeds autonomously through E0/E1 actions within the established contract and authority ceiling.
5. Governed deterministic execution is represented through existing research jobs and linked to the MWE.
6. Recovery and verification preserve failed attempts/evidence rather than overwriting them.
7. If E2 authority is required, persist/surface `USER ACTION REQUIRED` with the exact decision or authorization needed.
8. Before completion, verify required artifacts/provenance and the MWE completion contract.
9. Mark the MWE `COMPLETE` only after verification succeeds.
10. Produce a self-contained handoff to the receiving canonical thread; the canonical thread resumes research interpretation and roadmap authority.

## When to use Work

Use an MWE/Work when the task is substantial, multi-step, operationally bounded, benefits from autonomous continuation/recovery, and has a sufficiently frozen contract.

Prefer ordinary chat for small interactive analysis or when the user is actively making methodological choices. Use Automations for genuinely future/scheduled/conditional monitoring. Use governed GitHub Actions for deterministic compute rather than treating Work itself as the research-compute engine.

## Historical certification

The controlled evaluation W0-W9 completed successfully. The production pilot `MWE-PMPD-E3R2-001` is the certified historical MWE and is persisted as `HISTORICAL_VERIFIED_IMPORT`; synthetic W2/W3 MWE histories were intentionally not fabricated.

W9 production integration was certified through PR #53 and production merge SHA `e9bf54c511e280483672877fb552acf906e115ce`. Certification included authenticated MWE rendering, linked governed-job provenance, executor/SHA visibility, compute-policy visibility, read-only browser access, and production deployment verification.

## Known limitations

- Work orchestration is bounded by the tools/connections available to the active Work session.
- Ordinary chat execution is not background execution; persistent/future activity requires Work, an Automation, GitHub Actions, or another supported persistent mechanism.
- Authenticated UI paths may require a user-side browser verification when the execution environment cannot possess the user's login session.
- Free-compute/quota state is only as authoritative as the telemetry connected to the existing compute-provider control plane; do not infer remaining quota or literal billed dollars without evidence.
- MWE certification does not authorize research conclusions, production trading rules, or protected holdout/outcome inspection unless the canonical research gate separately authorizes them.

## Adoption decision

ChatGPT Work is **CERTIFIED FOR CONTROLLED MULtipLY OPERATIONAL ORCHESTRATION, WITH BOUNDED AUTHORITY**.

This standard is the baseline for future MULtipLY Work Envelopes. Material changes to the authority model, cost guardrails, canonical-thread ownership, or governed-execution separation require an explicit governance decision rather than silent drift.
