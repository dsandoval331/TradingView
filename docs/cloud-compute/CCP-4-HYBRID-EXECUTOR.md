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

## CCP-4 proof sequence

### CCP-4A — Routing policy

Implement and test deterministic routing:

`GitHub Actions -> Cloud Run (approved) -> Local Windows`

### CCP-4B — GitHub representative cloud job

Run one representative TradingResearch job in GitHub Actions using the certified CCP-3 container. The job must obtain its input data remotely rather than from the local Windows market cache, write deterministic evidence/artifacts, and retain Git SHA provenance.

### CCP-4C — Cloud Run adapter

Prepare the Cloud Run execution adapter and deployment contract without provisioning paid infrastructure. Provisioning/execution remains a separate explicit cost/account gate.

### CCP-4D — Local fallback worker

Expose a local worker path using the same job contract so overflow jobs can be executed locally with minimal manual interaction.

## Success criteria

CCP-4 is complete when:

1. routing policy tests pass;
2. GitHub-hosted representative research execution completes without the user's Windows machine;
3. remote input/output integrity and Git SHA provenance are certified;
4. Cloud Run is represented as a controlled secondary executor without bypassing spend approval;
5. the same job contract can fall back to local execution.

Google Cloud provisioning is not required merely to complete the GitHub-first portion of CCP-4; it remains an explicit infrastructure gate before first Cloud Run execution.
