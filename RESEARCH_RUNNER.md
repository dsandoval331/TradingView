# Trading Research Runner V1

A persistent local runner for large research batches. Code is versioned in GitHub; heavy historical computation stays on the local TradingResearch machine; standardized outputs are written under `research_outputs/`.

## Workflow

From the repository root with `.venv` active:

```powershell
git pull
python -m research_runner.runner status
python -m research_runner.runner run-next --project pmpd
```

To execute every pending registered PMPD job in sequence:

```powershell
python -m research_runner.runner run-all --project pmpd
```

The runner records local state at:

`research_outputs/runner/state.json`

Research artifacts are organized by project/job beneath:

`research_outputs/`

## V1 registered job

`PMPD-POST9N-B1` — contextual edge search around the frozen V5 DP4 event population. It tests gap context, time, geometry, opening/event-bar RVOL, SPY/QQQ alignment, and a small predeclared combination set. It does not modify V4, frozen V5, the completed 9N H2H result, or authorize production rules.

## Design direction

The registry is intentionally simple in V1. Future jobs can be added to `research_runner/jobs/` and registered in `runner.py`. The next infrastructure increment can add Supabase result/status publishing so ChatGPT can inspect compact research outputs without repeated file uploads.
