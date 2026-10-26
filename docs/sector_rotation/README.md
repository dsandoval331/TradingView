# MULtipLY — Sector Rotation Tracker v1

Canonical thread: Tool: Sector Rotation Tracker
MWE: MWE-SECTOR-V1-001
Authority ceiling: E1
Cost policy: ZERO_INCREMENTAL_COST_FIRST

## Product

Authenticated standalone route: `/dashboard/sector-rotation` in the existing
`apps/trading-research-web` app, linked from its control center. No second app,
Supabase project, paid data plan, or public data-sharing endpoint is created.

Date-by-sector heatmap defaults to the last 60 sessions and daily returns minus
SPY, in percentage points. Switch to price returns, ranks, or rank changes;
select a cell for daily / 5-session / 20-session detail. The leadership log tracks
changes in the strongest daily sector. CSV exports the displayed date window for
all 11 sectors and all metrics. Missing values remain empty. No illustrative data
is shipped with the dashboard.

Daily universe: SPY, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY.
S&P 500 sector ETF proxies are not the full US equity universe. These are price
leadership measurements, not institutional flows or validated trading signals.

## Data contract

Massive REST daily aggregates, `adjusted=true`: split-adjusted, not dividend
adjusted. Price returns can be affected by ex-dividend dates; do not describe
these as total returns. The existing GitHub `MASSIVE_API_KEY` or
`TR_MASSIVE_API_KEY` secret is reused. No provider upgrade is authorized.

The collector requests 729 calendar days through yesterday in America/New_York.
Free EOD data is available after midnight ET. GitHub Actions attempts collection
at 06:15 and 10:15 UTC Tuesday–Saturday (01:15/05:15 CT during daylight saving;
00:15/04:15 CT during standard time). The second run catches late data/outages.
GitHub scheduling can be delayed. A manual dispatch is also available.

Each run records the exact Git SHA, GitHub run ID, MWE reference, requested
window, response SHA-256 per symbol, coverage, and errors. Each changed/new bar
is appended in `sector_daily_observations`; unchanged history is not duplicated.
The full provider window is checked each time to catch historical split
restatements and corrections. Previous versions remain in the observations.
Only COMPLETE runs are published by `v_sector_daily_latest`, a security-invoker
view. Partial/failed runs cannot replace prior successful data. Supabase RLS
uses the existing MULtipLY user allowlist; no anonymous read or client write.

All 12 symbols must provide identical SPY-reference session dates, at least 25
bars, finite positive closes, and valid nonnegative volume. Pagination,
unadjusted responses, duplicate dates, invalid symbols, and stale history (>5
calendar days) fail closed. No synthetic prices or filling missing sessions.
The provider calendar is not an independent exchange-calendar certification.

Daily return = 100 × (close_t / close_previous_SPY_session − 1).
Relative return = sector daily return − SPY daily return (percentage points).
Ranks require all 11 valid sector returns; tied returns use competition ranks.
Rank improvement = previous rank − current rank. Horizons use 5 or 20 SPY
sessions and require uninterrupted sector observations over that interval.
The first available price date has no daily return and is omitted from history.
A spread below 0.25 pp is labeled mixed, an explicitly disclosed display rule.

## Operations and cost

Workflow: `.github/workflows/sector-rotation-daily.yml`.
Collector: `scripts/sector_rotation/collect.py` (Python standard library only).
Database schema: `sql/sector_rotation/sector_tracker_v1.sql`, applied remotely
using the named additive migration `add_sector_rotation_tracker_v1`.
The service-role secret stays exclusively in GitHub Actions; the app reads as
the authenticated user. No secret is printed, stored in source, or sent to the
client. Provider calls are spaced by 15 seconds with bounded 429/server retries.

Billing/quota telemetry was not independently verified. No new paid service is
provisioned. Existing account execution does not establish literal $0 billing.
No Cloud Run fallback, research runner modification, frozen data mutation,
protected research outcomes, or research-methodology changes are in scope.

## Verification

- `python3 -m unittest discover -s tests/sector_rotation -v`
- `node --test tests/sector_rotation/model.test.mjs` (Node 24)
- Existing Next.js build/type checking via the app's `npm run build`.
- Database RLS, grants, view security and successful-collection data readback.
- Authenticated browser verification where a valid session is available;
  never bypass the production user's allowlist for testing.

The MWE must report the actual deployed commit, workflow/run, data coverage,
verification limitations, and any external blocker before closure.
