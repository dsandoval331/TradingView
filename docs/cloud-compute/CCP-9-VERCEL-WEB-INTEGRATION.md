# CCP-9 — Vercel Web App Integration

## Objective

Expose the governed cloud-compute control plane through the authenticated TradingResearch web application without weakening the execution, provenance, or zero-incremental-spend controls certified in CCP-8.

## Web submission flow

1. An authenticated and allowlisted TradingResearch user opens `/dashboard/cloud-compute`.
2. A server action validates the requested runner against the CCP-9 fixture allowlist.
3. The server records a `research_jobs` row with the Vercel deployment Git SHA, `github_actions` as preferred executor, and `cloud_run_spend_approved=false`.
4. The server dispatches `.github/workflows/ccp9-web-job.yml` with the exact `job_id` and `git_sha`.
5. GitHub Actions checks out that exact SHA and verifies it before execution.
6. The worker claims the exact submitted job through `claim_research_job_by_id_v1`.
7. The governed autonomous loop may retry the same job or run explicitly defined successors, subject to the CCP-8 limits and stopping gates.
8. Job status, timestamps, errors, attempts, logs, and artifacts remain persisted in Supabase and the web page reads the live control-plane state.

## Security boundaries

- Browser clients never receive the Supabase server secret or GitHub Actions token.
- `SUPABASE_SECRET_KEY` and `TR_GITHUB_ACTIONS_TOKEN` are server-only environment variables.
- The exact-claim RPC is executable only by `service_role`; public, anon, and authenticated roles are revoked.
- User authentication and `is_trading_research_web_user` allowlisting are checked before server-side job submission or control-plane reads.
- The web UI does not accept a Git SHA from the user. It uses the deployment SHA (`VERCEL_GIT_COMMIT_SHA`) or an explicitly configured server-only fallback.
- CCP-9 exposes deterministic platform fixtures only. Research-lane runner enablement is deferred to CCP-10.
- Every CCP-9 web-created job explicitly sets `cloud_run_spend_approved=false`.

## Required Vercel server environment

Existing public variables:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`

Additional server-only variables:
- `SUPABASE_SECRET_KEY`
- `TR_GITHUB_ACTIONS_TOKEN`
- `TR_GITHUB_REPOSITORY` (defaults to `dsandoval331/TradingView`)

Vercel Git deployments provide the deployment commit SHA/ref. Local or non-Git environments can use server-only `TR_GIT_SHA` and `TR_GIT_REF` fallbacks.

The GitHub token should be narrowly scoped to the repository and only the permissions required to dispatch Actions workflows. Never prefix either secret with `NEXT_PUBLIC_`.

## Certification gates

CCP-9 is complete only after all of the following are demonstrated:

- Python control-plane and autonomous-loop contract tests pass.
- TradingResearch web TypeScript typecheck and production build pass.
- Supabase security advisor shows the CCP-9 exact-claim function did not introduce a new authenticated SECURITY DEFINER exposure or mutable search-path warning.
- A real authenticated Vercel-hosted submission creates a Supabase job, dispatches GitHub Actions, checks out the recorded SHA, claims that exact job, completes it, persists logs/artifact/checksum, and exposes the resulting status back through the web application.

Until the final live Vercel-hosted submission is certified, CCP-9 remains ACTIVE.
