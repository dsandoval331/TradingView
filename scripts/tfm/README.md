# TFM Trading — MWE-SECTOR-TFM-001

Canonical thread: **Tool: Sector Rotation Tracker**. Authority: E1. Cost policy: ZERO_INCREMENTAL_COST_FIRST.

## Contract

`rules.json` is frozen in `public.tfm_rules` before the first real outcome evaluation. Canonical sorted JSON SHA-256: `3a63191b150b428782b29d3c375c0b80d98fea0af3c2ddee0f4c3907b7e61426`.

The strict bearish pattern is Friday high below Thursday high; Monday low below Friday low is a hit. Exact equality fails. An actual Monday exchange holiday substitutes Tuesday, with an independent UI cohort. Missing symbol/benchmark bars do not imply holidays. Literal Thursday and Friday must both be sessions. Early closes are included. Calendar: 2021–2027, including the January 9, 2025 extraordinary closure; outside this horizon fails closed.

Universe: all 11 sector ETFs plus the **51 share classes** in the app's existing Top 50 snapshot dated 2026-10-23. SPY is context only. Frozen current membership is subject to survivorship bias; this does not represent historical index membership. No protected research tables are read or modified.

### Metrics

- Pattern hit rate: hits / completed qualifying setups. Missing target sessions never count as misses.
- Baseline: all eligible same-symbol triplets under the same cohort, dates, asset and origin filters, with no lower-high condition. Nonqualifying control rate is also shown.
- MFE: max(0, (target open − target low) / target open) × 100.
- MAE: max(0, (target high − target open) / target open) × 100.
- These are whole-target-session descriptive excursions, not executable entry simulations or P&L. Gap-through means target open strictly below Friday low; a hit can have zero subsequent favorable movement.
- Market condition: SPY Friday close versus EMA20, initialized at the first valid source bar, requiring the last 20 exchange sessions. No target-day data is used.
- Pooled symbol-weeks are correlated. No independent-trial significance or causal edge claim is made.

Historical range requested: 2021-11-03 to 2026-11-02. Existing sources cover about two years. Five-year certification remains false; the scanner cannot certify it merely from dates. No synthetic backfill is allowed.

## Persistence and recovery

`tfm_rules`, `tfm_runs`, `tfm_setups`, `tfm_outcomes` have RLS and allowlisted authenticated read access. Only the server-side service role can insert. Setups and outcomes cannot be updated/deleted by that role. `tfm_publish_scan` publishes all new rows and completes the run in one transaction. Failed publications expose no partial batch.

First reference snapshots, first outcomes, original record timestamps, source collection IDs and raw-response hashes are retained. Reruns append only missing keys. Restated references block new outcomes for the affected setup; existing historical records are preserved and correction counts are displayed. Source corrections require a separately versioned review, not silent rewriting.

Origins are assigned at actual recording time: only after Friday close and before target open is prospective. Backtests are always historical and cannot become prospective on rerun.

## Execution

`python3 scripts/tfm/scan.py` reads the existing `TR_SUPABASE_URL` and `TR_SUPABASE_SECRET_KEY` GitHub secrets via workflow environment variables. It makes **zero market-provider requests**. It paginates operational views, verifies source hashes and the frozen contract, and logs a durable run ID and coverage.

`.github/workflows/sector-tfm.yml` runs a credential-free initial branch test and configures Tuesday–Saturday 09:15/13:15 UTC scans after existing stock collector starts at 08:15/12:15 UTC. Secret-bearing scans require reviewed code on main; scheduled runs require the workflow on the default branch. A new feature branch alone does not enable recurring scans. Daily source-plan latency can delay Friday discovery until the next morning; this is not a real-time or guaranteed Friday-close feed.

The repository is public and the workflow uses standard `ubuntu-latest`, with no artifact/cache uploads or paid provider calls. GitHub documents free standard public-repository runner use. This is a runner-price entitlement, not proof of account-wide billed $0 or of Supabase/Vercel invoice totals. No paid source, plan upgrade, or new paid compute is authorized.

## Checks

- `python3 -m unittest discover -s tests/tfm -p 'test_*.py' -v`
- `node tests/tfm/test_model.mjs` (Node 24; native TypeScript stripping)
- `npm ci --ignore-scripts --no-audit --no-fund` then `npm run build` in `apps/trading-research-web`

Deployment/authenticated UI verification, first real run results and five-year data-source feasibility must be reported with their actual status; none is implied by a build passing.
