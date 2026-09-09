# CCP-3 — Containerized Research Runner

## Objective
Package the existing `research_runner` execution contract for local Docker and future Cloud Run Jobs without changing research logic or governance.

## Runtime contract
- Code lives at `/app`.
- Mutable runtime state/data lives under `TR_WORK_ROOT=/workspace`.
- The image contains code and pinned Python dependencies only.
- Market data, research outputs, secrets, credentials, and local virtual environments are excluded from the image build context.
- Default command is `python -m research_runner.runner status`.
- A job can be selected by overriding command arguments, for example `run-next --project pmpd`.
- Container builds must inject the source revision with `--build-arg TR_GIT_SHA=<sha>` so provenance does not depend on copying `.git` into the image.
- Image construction runs `python -m cloud_compute.container_contract`; missing workspace separation or source provenance fails the build.

## Local certification
From the repository root:

```powershell
$sha = git rev-parse HEAD
docker build --build-arg TR_GIT_SHA=$sha -f Dockerfile.research -t trading-research-runner:ccp3 .
docker run --rm trading-research-runner:ccp3
```

Expected smoke-test invariants:
- `CODE_ROOT=/app`
- `WORK_ROOT=/workspace`
- `GIT_SHA` equals the build argument
- registered jobs report READY in a clean workspace

The container intentionally does not contain market data or credentials. Later job execution will receive required runtime datasets and outputs through the cloud data/artifact layer rather than image contents.

## Cloud migration
The same image is intended for CCP-4 Cloud Run Jobs. CCP-4 will add cloud-side dataset acquisition/mounting and artifact publication around this unchanged runner contract.

## Governance
Containerization does not alter frozen strategy/model definitions, evidence classifications, validation rules, or trading logic. Local Windows execution remains supported.
