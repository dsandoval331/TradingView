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

## Certification target

The live CCP-7 certification request uses `CCP3-PARITY-FIXTURE` and `CCP7-SUBMISSION-CERT-1`. PASS requires one GitHub push to a request manifest to produce, without manual Supabase job creation:

1. a new queued control-plane job,
2. exact SHA provenance equal to the workflow checkout,
3. GitHub execution of the requested runner job,
4. successful attempt lifecycle,
5. persisted structured logs,
6. checksum-verified primary artifact registration.

## Remaining hardening before autonomous research

Atomic database job claiming remains a CCP-8 prerequisite so simultaneous workers cannot race on the same queued job. Attempt numbering should also be derived atomically rather than relying only on mutable request metadata.
