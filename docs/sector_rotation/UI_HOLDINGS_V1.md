# MULtipLY — heatmap axes and ETF holdings

Thread: Tool: Sector Rotation Tracker
MWE: MWE-SECTOR-UI-001
Authority: E1 | ZERO_INCREMENTAL_COST_FIRST

User requested switching heatmap axes and listing the top five ETF stocks with
their percentages in the detail section beneath the heatmap on mobile.

## Result

Both main-sector and Tech & AI heatmaps now use ETF/group rows and date columns,
newest date at the left. Group labels and date headers remain sticky. Cell
selection still selects both the group and session; row labels select the group,
and date headers select the session. Horizontal scrolling exposes older dates.
No return, rank, basket composition, benchmark, CSV calculation, or data-pipeline
logic changes.

The selected-group detail section includes a stock/weight table. Each of the 11
sector ETFs and IGV has five issuer-sourced stock positions, in issuer order,
with percentage of the WHOLE fund, not renormalized to the top-five subset.
The combined top-five percentage, issuer as-of date, source link, and review date
are visible. Separate Alphabet share classes remain separate fund positions.

The three custom baskets show every member and its equal daily target weight.
They are labeled custom baskets and do not invent a top-five ranking among equal
weights. Six-member baskets display 16.67% per member due to rounding; raw target
weights sum to 100%.

## Holdings source and freshness

Snapshot file: `apps/trading-research-web/app/dashboard/sector-rotation/holdings.json`.
State Street sources: the issuer's Fund Top Holdings tables (NOT Index Top
Holdings), as of 2026-10-22. IGV: iShares latest fund holdings CSV, as of
2026-10-23. All snapshots reviewed 2026-10-25. Every record includes its official
source URL. The application labels them dated snapshots. Historical price-date
selection never implies historical holdings membership.

This bounded UI change does NOT introduce automatic holdings refresh. The
existing overnight price collectors remain independent. Refreshing holdings
requires reviewing the issuer snapshots and updating the versioned source file;
do not imply a recent price update also refreshed holdings.

## Verification

- All 12 ETF records checked for exactly five positive, descending weights;
  totals no greater than 100%, with issuer source and as-of date.
- Existing model checks run without changing their expectations.
- Full Next.js production build verifies component integration.
- Signed-in browser interactions remain unverified when no authenticated
  MULtipLY browser session is available. No auth bypass is introduced.
