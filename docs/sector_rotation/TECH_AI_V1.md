# MULtipLY — Tech & AI detail v1

Thread: Tool: Sector Rotation Tracker
MWE: MWE-SECTOR-TECH-001
Parent: MWE-SECTOR-V1-001 (completed; original sector contract preserved)
User request: add software vs hardware and AI semiconductors vs non-semiconductors.
Authority: E1 | ZERO_INCREMENTAL_COST_FIRST

## Display groups

| Group | Definition | Weighting |
|---|---|---|
| Tech Software | IGV ETF; software plus selected interactive media/services | ETF issuer weights |
| Tech Hardware | AAPL, DELL, HPQ, HPE, ANET, CSCO, STX, WDC | 1/8 each daily |
| AI / Semiconductors | NVDA, AMD, AVGO, MRVL, MU, TSM | 1/6 each daily |
| AI / Non-semiconductors | MSFT, GOOGL, AMZN, META, ORCL, PLTR, ANET, VRT | 1/8 each daily |

These are selected monitoring groups, not four disjoint official sectors. ANET
belongs to Hardware and AI / Non-semiconductors. The latter means primary
businesses outside semiconductor production; cloud providers can also design
custom chips. AI chip members earn non-AI revenue too. Hardware includes devices,
servers, networking and storage; it is not an exhaustive industry index.

Constituents were selected on 2026-10-25 for this version. Historical calculations
show this CURRENT selected basket viewed retrospectively. They are not a
point-in-time reconstruction of AI membership, free of selection/survivorship
bias, or a strategy backtest. New constituent versions must be named and dated;
never silently rewrite membership. See `tech-ai/groups.json` for the manifest.

Software uses the IGV ETF. Do not substitute AIQ as an ex-chip AI proxy: the
issuer's holdings include semiconductor companies. Do not use XTH as a current
hardware ETF: its issuer announced liquidation in 2020.

## Calculations

For each basket, daily return is the arithmetic mean of all member stocks'
split-adjusted close-to-close price returns for that SPY session. Equal weights
are reset at each session boundary. A synthetic index begins at 100 and compounds
those daily basket returns. Five- and twenty-session returns are compounded
basket returns, not simple means of each member's multi-session performance.
The synthetic index is not a tradable market price. No dividends, fees, turnover
costs, or trading assumptions are included.

If any constituent/session is missing, do not fill, reweight the remaining
members, or bridge the gap. Interrupt the index and suppress returns spanning
the interruption. The complete-universe ranks in this view compare only four
groups. Main-sector default membership and rankings remain the original 11.

## Isolated ingestion and access

The 23-symbol collector uses the same existing Massive API credential, the
standard Python library, and append-only storage. It does not read research
holdouts or modify frozen datasets. Separate tables (`tech_tracker_runs`,
`tech_daily_observations`) and `v_tech_daily_latest` prevent a new-theme source
failure from blocking the existing sector pipeline. RLS uses the existing
MULtipLY allowlist; anonymous reads and browser writes are not granted.

Workflow: `.github/workflows/sector-tech-ai-daily.yml`.
Schedule: 07:15 and 11:15 UTC Tuesday–Saturday, one hour after the original
sector collection times to reduce shared-provider rate contention. Both collectors share the GitHub
concurrency group `sector-rotation-data` to serialize their API use when
schedules overlap. Only
completed provider days are requested. GitHub schedules may be delayed.
Up to 23 provider calls per pass are spaced 15 seconds apart, with bounded
retry on throttling/server errors. A 20-minute job timeout bounds execution.

No new paid service, upgrade, or paid fallback is provisioned. Existing billing
and quota telemetry do not establish literal $0 charges.

## Source references

- Software ETF issuer: https://www.ishares.com/us/products/239771/IGV
- Broad AI ETF holdings: https://www.globalxetfs.com/funds/AIQ
- Semiconductor ETF scope (broad chips, not pure AI): https://www.vaneck.com/us/en/investments/semiconductor-etf-smh/
- NVIDIA data-center/AI infrastructure: https://www.nvidia.com/en-us/data-center/
- Micron AI memory/storage: https://www.micron.com/markets-industries/ai
- Arista AI networking: https://www.arista.com/en/solutions/ai-networking
- XTH liquidation filing: https://www.sec.gov/Archives/edgar/data/1064642/000119312520148769/d906322d497.htm

Company inclusion is the tracker author's current monitoring definition, not a
claim that the issuer or an official index provider has certified this basket.

## Verification

Run existing model and collector checks plus
`node --test tests/sector_rotation/tech-model.test.mjs` on Node 24.
The full Next.js build checks the new authenticated `/dashboard/sector-rotation/tech-ai`
route. Verify 23-symbol aligned backfill, independent equal-weight calculations,
RLS/grants, live deployment and explicit browser QA limitations before closure.
