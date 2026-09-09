# Trading Research Cloud Compute Platform

Roadmap: `CLOUD-COMPUTE-RM-1.0`

## Objective

Move heavy TradingResearch batch execution toward a reproducible cloud environment while preserving the existing Windows workflow for development, fallback, validation, and archival reproduction.

Cloud migration is an execution-environment change. It must not alter frozen strategy definitions, evidence classifications, research protocols, or validation rules.

## Zero-incremental-cost-first baseline

Initial implementation reuses services already in the TradingResearch stack wherever possible:

- GitHub for source/version control.
- Existing Supabase Pro project for the research/control-plane database and the initial object-storage proof of concept.
- Existing Vercel application for UI/control surfaces only, not heavy batch compute.
- Google Cloud Run Jobs remains the preferred batch-compute target, subject to a later explicit account/billing/credential gate and free-tier benchmark.
- Local Windows execution remains supported.

No paid add-on, additional Supabase project, spend-cap change, or intentional quota overage is part of this baseline.

## Local/cloud path contract

`research_runner` distinguishes two roots:

- `CODE_ROOT`: checked-out Git repository containing Python modules and Git metadata.
- `WORK_ROOT`: runtime filesystem containing market data, research inputs/outputs, artifacts, and runner state.

By default `WORK_ROOT == CODE_ROOT`, preserving existing local behavior. A container or other remote executor can set `TR_WORK_ROOT` to an ephemeral/staged directory without modifying individual research jobs immediately.

Expected work-root layout:

```text
<WORK_ROOT>/
  market_cache/
    MARKET_CACHE_V1/
      1m/<SYMBOL>/<YEAR>.parquet
  research_outputs/
    runner/state.json
    ...project artifacts...
```

The Git SHA is always resolved from `CODE_ROOT`; job modules receive `WORK_ROOT`.

## Initial cloud storage layout

For the initial Supabase Storage POC, preserve the local dataset identity and symbol/year partitioning:

```text
MARKET_CACHE_V1/
  1m/
    AAPL/2025.parquet
    AAPL/2026.parquet
    SPY/2025.parquet
    ...
```

Storage is private. Dataset versions are treated as immutable logical releases. Supabase Storage does not provide S3 object versioning, so changed canonical datasets must use a new cache/dataset version rather than silently replacing a certified version.

A manifest records every object's relative path, size, and SHA-256. Cloud/local parity is certified by comparing manifests/hashes, not by trusting filenames alone.

### CCP-2 representative parity POC

The first live POC uses only:

- `1m/SPY/2025.parquet`
- `1m/SPY/2026.parquet`
- `1m/AAPL/2025.parquet`

Validate the local selection without credentials:

```powershell
python -m cloud_compute.storage_poc --dry-run
```

A live run requires `SUPABASE_URL` and a server-side `SUPABASE_SECRET_KEY` in the process environment. Never commit or print the secret key. The POC uploads without overwrite, downloads each private object back to a temporary directory, recomputes size and SHA-256, and fails if byte/hash parity differs.

```powershell
$env:SUPABASE_URL = "https://<project-ref>.supabase.co"
$env:SUPABASE_SECRET_KEY = "<server-side-secret>"
python -m cloud_compute.storage_poc
```

For a repeat verification of already-uploaded immutable objects:

```powershell
python -m cloud_compute.storage_poc --allow-existing
```

The default evidence record is written to:

`research_outputs/cloud_compute/ccp2/storage_poc.json`

The script never writes credentials into the evidence file.

## CCP-1 measured baseline — 2026-09-09

- Local canonical cache: `market_cache/MARKET_CACHE_V1`
- Compressed size: approximately 0.93 GB
- Files: 280
- Largest observed partition: approximately 10.71 MB
- Local runner baseline SHA observed: `e42ec78ab50230fa3d16a757da50b0124d572f48`
- GitHub `main` had advanced beyond the local baseline during inventory, demonstrating why Git SHA must be part of every cloud job record.

At this size, the canonical cache consumes roughly 1% of Supabase Pro's 100 GB included Storage quota before considering other organization usage. The project must still monitor quota/egress and keep the Pro Spend Cap enabled for covered usage.

## Migration sequence

1. CCP-1 — architecture, inventory, zero-cost baseline.
2. CCP-2 — private cloud-data POC; upload a small representative subset first, create a manifest, download it, and prove byte/hash parity.
3. CCP-3 — containerize the existing runner and prove local native vs local-container parity.
4. CCP-4 — execute one real research job on the selected cloud batch executor.
5. CCP-5 onward — durable Supabase job control plane, artifacts, automation, web UI, lane migration, reliability/cost certification.

The platform does not authorize automatic changes to research hypotheses, frozen models, or production trading logic.
