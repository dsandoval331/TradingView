# TFM Trading v2 — MWE-SECTOR-TFM-001

Canonical thread: **Tool: Sector Rotation Tracker**. Authority: E1. Cost policy: ZERO_INCREMENTAL_COST_FIRST.

## Contract

`rules.json` is frozen in `public.tfm_rules` before the first real outcome evaluation. Canonical sorted JSON SHA-256: `86ed9d54dfc225da2869da5b53c126ef4a325243b79796ca8881d17222f8ae19`.

The strict bearish pattern is Friday high below Thursday high; Monday low below Friday low is a hit. Exact equality fails. An actual Monday exchange holiday substitutes Tuesday, with an independent UI cohort. Missing symbol/benchmark bars do not imply holidays. Literal Thursday and Friday must both be sessions. Early closes are included. Calendar: 2021–2027, including the January 9, 2025 extraordinary closure; outside this horizon fails closed.

Universe: all 11 sector ETFs, the **51 share classes** in the app's existing Top 50 snapshot dated 2026-10-23, and the IGV ETF plus actual Tech & AI member stocks. Overlapping stocks are counted once. Synthetic baskets are never scored from invented OHLC. SPY is context only. Frozen current membership is subject to survivorship bias; this does not represent historical index membership. No protected research tables are read or modified.

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

## Revised page layout (user request)

TFM Trading is a sibling tab of Market Overview, Event Log and Swing Trades on Main Sectors, Tech & AI detail and S&P 500 Top 50 Index. Main Sectors is restricted to the 11 sector ETFs; other pages load only their own actual tradable symbols. The old standalone route redirects to the Main Sectors TFM tab.

Each page has independent **Live results** (prospective origin only) and **Historical results** (historical origin only) aggregates. Live lifetime statistics include prior months. Only the current target-session month shows instance rows initially; older months are retained in a collapsed archive with per-month statistics. Historical individual occurrences are never rendered. Target-month grouping means an October Friday with a November Monday belongs in November.

V1's frozen database contract remains unchanged; the explicitly requested extra Tech & AI universe is recorded as tfm-bearish-v2. Initial backfill remains historical; only setups recorded before their target open can enter live tracking.

Additional check: `node tests/tfm/test_ui.cjs` verifies SSR visibility with synthetic fixtures after app dependencies are installed.

## Authorized six-month load, 2026-11-04

User requested target sessions May 4–November 3, 2026 and a separate check of October 29–30. The actual source boundary is November 2, covering the latest target session. No website merge or publication is required for this data load.

Primary deterministic computation runs directly on existing Supabase Postgres using `backfill_20261104_six_months.sql` (DIRECT GOVERNED EXECUTION). `prepare_sql_backfill.py` independently verifies the full exchange calendar, source OHLC and response hashes, SPY EMA category, strict pattern/gap booleans and excursion formulas, then packages the existing atomic publication RPC. JSON integral-float canonicalization makes equivalent SQL/REST numbers produce stable hashes; the frozen rule contract hash is unchanged. All loaded instances are HISTORICAL. No market-provider requests, paid resources or live brokerage actions are involved.

All 72 actual symbols have all 25 eligible weeks (1,800 complete triplets). Reference bars before May 4 are retained solely to score the first target week. Five-year coverage is still unverified. Forward tracking remains separate and starts only when setups are actually recorded before the target session.

Routine scans begin at the earliest already-recorded Friday when records exist. They settle/append forward records without silently expanding the authorized six-month historical cohort. Any older backfill remains a separate operation.

## Monthly instances and release authorization

User explicitly authorized production/main release and showing the October 29–30 / November 2 historical instances in the current month. Monthly assignment now uses the nominal Monday (Friday + 3 days), including when the observed outcome is on holiday Tuesday. Thus May 31 Monday / June 1 Tuesday belongs to May. Monthly tracking starts with Monday 2026-11-02. Those imported historical records remain immutable HISTORICAL and stay out of forward-only lifetime statistics; they remain visible in the monthly archive after the month rolls over. Older backtest instances remain aggregate-only.

## Live-results population correction

User clarified that the monthly tracking period must populate Live Results and must be excluded from Historical Results. Live Results now includes every eligible symbol-week whose nominal Monday is November 2, 2026 or later, irrespective of recording origin. Historical Results includes only nominal Mondays before that boundary. These are disjoint time cohorts. Imported instances keep HISTORICAL origin, collection provenance and actual recording timestamps; UI explicitly states that the tracking totals include imports and are not a wholly prospective signal-performance record. Pattern, baseline and excursion formulas are unchanged.

## Alternate success — user approved 2026-11-04

Exploratory secondary measure `tfm-alternate-v1-exploratory`: a qualifying setup is an alternate success only if the original Friday-low test failed, whole-target-session MFE >= 0.5% and MFE/MAE >= 2. Primary success always takes precedence; combined counts cannot double count. Positive MFE / zero MAE has infinite ratio; zero/zero is undefined. Invalid data or thresholds cannot qualify. Pending outcomes are excluded from denominators.

Thresholds are configurable per view, reset on reload to approved defaults, and apply uniformly to live, historical and archived monthly summaries and instance classifications. Source outcomes, original hit flags, immutable origins, dates and provenance are not rewritten. Retrospective statistics are explicitly exploratory because criteria were selected after outcome inspection; prospective-origin alternate performance is shown separately. Daily OHLC cannot establish excursion order, fills, stop behavior or realized profitability.


## Ranking & Research XP v1 — approved 2026-11-04 | 09:32 PM CT

Thread: Tool: Sector Rotation Tracker. MWE-SECTOR-TFM-001, E1, ZERO_INCREMENTAL_COST_FIRST. User approved the concrete v0.1 proposal: 70/20/10 Friday priority weights, top-five/100×NDCG@5 reviews, and 30 XP/week process rewards. This is a new prospective pilot, not a validated probability model. Existing primary/alternate result definitions and historical data stay unchanged. First eligible nominal Monday is 2026-11-09; capture must actually occur before target open.

Canonical specification/change log: https://chatgpt.com/library?file_id=libfile_7757730a1c908191a4b5838df1510418&account_id=personal

Applied migration `20261105033401_tfm_ranking_v1.sql` introduces append-only model registry, pre-open snapshots, full-pool verified reviews, a weekly XP ledger and saved reflections. Source SQL is also kept in `ranking_v1.sql`. Full precision score sorts descending, close-to-low distance breaks ties, then ticker. Missing/invalid reference bars and zero ranges are UNRANKABLE. All source/membership/model hashes and recording times are retained. Complete baseline membership is required to freeze each of the three scopes, including its nonqualifiers. Empty candidate pools receive no invented rates or NDCG.

The existing `sector-tfm.yml` job now calls `tfm_process_rankings` after successful scan publication. A rank transaction failure leaves the valid underlying scan published and fails the workflow for recovery. Read-only synthetic RPC checks verify the deployed scoring contract on each run. Scans cannot create retrospective prospective ranks; already-viewed November 2 outcomes never receive v1 ranks or XP. Verified reviews use immutable 0.5%/2:1 alternate defaults, independent of temporary UI settings. Pending outcomes and detected corrections withhold final review; missing higher ranks are never replaced by completed lower ranks. Holiday-Tuesday results and season statistics remain separate.

XP awards are once per nominal Monday across all three pools: complete on-time freeze 10, verified full review 10, provenance/completeness evidence 5, and an actual saved reflection 5. A composite primary key and generated point values prevent duplicate rewards and enforce the weekly cap. Reflections require an allowlisted authenticated author, a completed review, and 20–4,000 characters; the bounded function uses a fixed empty search path and rejects anonymous callers. Other rank tables are read-only to allowlisted users, with no update/delete grants to the scanner. The account starts at 0 XP; outcomes do not affect process rewards.

Dashboard additions: frozen score explanations and audit record, top-five/pool/lift/NDCG cards, separate Monday/holiday seasons, blind instance-outcome reveal, weekly mission, shared XP, four cosmetic levels, earned evidence-based milestone badges, saved reflection and collapsed past weeks. Challenger competitions, confidence calibration, themes and advanced badges remain later extensions; they are not represented as deployed.

Validation: 16 Python engine/scanner tests; existing and ranking SSR fixtures; TypeScript model checks; production Next build; deployed SQL contract checks; and temporary-table integration exercising three-pool freeze, pending reviews, verified reviews, idempotent 10/25 XP totals and late-start rejection, with all fixtures rolled back. The new reflection definer RPC is an intentional, allowlist-guarded authenticated endpoint; no anonymous execute grant. Existing unrelated database advisories remain out of scope. Authenticated interactive browser verification has not been performed in this workspace.

Rollback: revert app/scanner code to the previous release; retain the append-only tables/model/evidence and stop ranking writes. Do not delete frozen research history or silently rewrite v1. Any selection/evaluation revision requires a new approved model and a future effective week, recorded in the same specification/change log.


## Excursion statistics by outcome — 2026-11-05 | 02:14 AM CT

User requested MFE/MAE for primary misses, alternate successes and all qualifying instances. The existing mean MFE/MAE card already used all completed qualifying instances; its label now makes this explicit. Each stats block also shows counts and separate arithmetic means for (1) pattern hits, (2) primary misses including alternate successes, (3) alternate successes under the current view thresholds, and (4) all completed qualifying instances. Alternate successes overlap the primary-miss group; the four rows must not be summed. Pending outcomes and nonqualifiers are excluded. Empty groups show unavailable means; invalid alternate thresholds show unavailable alternate-group stats while primary-hit/miss/overall means remain available.

The shared stats component applies this comparison to all three page scopes, live/historical summaries, separate Monday/holiday-Tuesday cohorts and expanded previous-month summaries. No source data, ranking weights, success criteria, frozen reviews or XP rules change. Validation: exact model fixtures for all four groups, pending/nonqualifier exclusions, empty groups and invalid/custom alternate thresholds; SSR fixtures checking group labels, counts and means on all three scopes; production Next.js build. Roll back the display/model helper to the previous release if needed; no data rollback is required. Strategy documentation patch v1.0.1 records this reporting clarification.
