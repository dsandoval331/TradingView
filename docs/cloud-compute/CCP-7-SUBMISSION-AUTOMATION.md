# CCP-7 — GitHub to Cloud Submission Automation

## Objective

Eliminate the manual two-step process of creating a Supabase research job and separately starting a GitHub worker. A governed GitHub request manifest should create the control-plane job with the workflow commit SHA and then execute that same job in the same GitHub Actions run.

## Contract

A request manifest under `.github/cloud-job-requests/*.json` defines the runner job, project/phase, dataset version, executor, priority, and optional parameters. The GitHub workflow injects its own `github.sha` as `TR_GIT_SHA`; request manifests cannot override provenance.

`cloud_compute.submit_job` validates the request and inserts a queued `research_jobs` row. The workflow then invokes `cloud_compute.control_plane_worker` from the same checkout.

## Governance and cost controls

- GitHub Actions is the default executor.
- Cloud Run remains fail-closed unless the request explicitly carries `cloud_run_spend_approved=true`.
- The worker only executes queued jobs whose declared `git_sha` exactly matches the checked-out runner SHA.
- Supabase remains the control plane; research artifacts and structured logs continue to be persisted by the CCP-6 worker contract.

## Live certification

CCP-7 passed live certification on GitHub Actions run `34433355788` from request commit `fca36758d279875bbf46e85b8079b7249eed24d8`.

The request manifest automatically created Supabase job `90d3e856-4302-4d9d-a0a4-8b9a401679ef` with dataset version `CCP7-SUBMISSION-CERT-1`. The job and attempt both recorded the same exact Git SHA as the workflow checkout and completed successfully with exit code `0`.

Attempt: `e178783f-5215-4d6c-ada7-5ccaa888bba1`.

Primary artifact: `41c33291-e8d5-489a-b9d5-28575d4277db`, 82 bytes, SHA-256 `b0626ac4532a467dad8076fdee7a0e197c2d00d8afa2b075bea671941d1c10f6`.

Structured runner logs were persisted with ordered sequence numbers and the deterministic parity fixture passed.

Disposition: **COMPLETE → CCP-8 Governed Autonomous Research Loop**.

## Remaining hardening before autonomous research

Atomic database job claiming remains a CCP-8 prerequisite so simultaneous workers cannot race on the same queued job. Attempt numbering should also be derived atomically rather than relying only on mutable request metadata.
