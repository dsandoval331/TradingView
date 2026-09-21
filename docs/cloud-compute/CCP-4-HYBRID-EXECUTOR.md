# CCP-4 — Hybrid Cloud Runner Proof of Concept

## Objective

Prove that TradingResearch jobs can be routed through a common execution contract without changing research logic, provenance, datasets, or governance.

## Executor priority

1. `github_actions` — primary remote executor while included/free capacity is available.
2. `cloud_run` — secondary remote executor for overflow/scale, but only when explicitly enabled under the project spend guardrail.
3. `local_windows` — tertiary fallback for development, recovery, parity validation, archive, or when remote capacity is unavailable.

## Cost guardrail

Cloud Run must never be selected merely because it is technically reachable. It is eligible only when the control plane marks both:

- Cloud Run available; and
- cloud spend explicitly approved for the applicable operating window/budget.

This preserves `NO_INCREMENTAL_SPEND_WITHOUT_EXPLICIT_APPROVAL`.

## Common execution contract

Every executor must preserve the same:

- research job identifier;
- Git SHA / container provenance;
- project and phase;
- configuration;
- dataset version and object checksums;
- `research_runner` job implementation;
- result schema;
- artifact checksums;
- status transitions and failure metadata.

Executor choice is infrastructure metadata, not research methodology.

The executor-neutral CLI entrypoint is:

```text
python -m research_runner.runner run-id <JOB_ID>
```

GitHub Actions, Cloud Run, and the local fallback worker all target this same job-id contract.

## CCP-4 proof sequence

### CCP-4A — Routing policy — COMPLETE

Implemented and GitHub-certified deterministic routing:

`GitHub Actions -> Cloud Run (approved) -> Local Windows`

### CCP-4B — GitHub representative cloud job — COMPLETE

Certified on GitHub Actions using the CCP-3 container and a remotely checked-out representative market-data fixture. The run completed without the user's Windows machine, retained Git SHA provenance, validated deterministic results, and uploaded evidence artifacts.

Certification run: `34396382642`.

### CCP-4C — Cloud Run adapter — IMPLEMENTED / PROVISIONING GATED

`cloud_compute.cloud_run_adapter` now defines the Cloud Run deployment/execution contract. It does not provision infrastructure itself. Both deploy and execute command generation fail closed unless explicit spend approval is present.

The adapter invokes the same `research_runner ... run-id <JOB_ID>` contract used by other executors. First live Cloud Run deployment remains a separate explicit account/cost gate.

### CCP-4D — Local fallback worker — IMPLEMENTED

`cloud_compute.local_worker` exposes a minimal local fallback path that executes one job by exact job ID, or the next eligible project job, through the same `research_runner` functions. This avoids maintaining separate local research logic.

Example future fallback invocation:

```powershell
python -m cloud_compute.local_worker --job-id <JOB_ID>
```

## Success criteria

CCP-4 is complete when:

1. routing policy tests pass;
2. GitHub-hosted representative research execution completes without the user's Windows machine;
3. remote input/output integrity and Git SHA provenance are certified;
4. Cloud Run is represented as a controlled secondary executor without bypassing spend approval;
5. the same job contract can fall back to local execution.

Google Cloud provisioning is not required for the software-contract portion of CCP-4; first live Cloud Run deployment remains an explicit infrastructure/cost gate.
