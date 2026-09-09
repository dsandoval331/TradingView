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

## Local smoke test
```powershell
docker build -f Dockerfile.research -t trading-research-runner:ccp3 .
docker run --rm trading-research-runner:ccp3 status
```

To exercise a job against an explicitly mounted workspace, mount only the required runtime data and outputs. Do not bake credentials or market data into the image.

## Cloud migration
The same image is intended for CCP-4 Cloud Run Jobs. CCP-4 will add cloud-side dataset acquisition/mounting and artifact publication around this unchanged runner contract.

## Governance
Containerization does not alter frozen strategy/model definitions, evidence classifications, validation rules, or trading logic. Local Windows execution remains supported.
