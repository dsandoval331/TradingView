# Suggested Swing Trades (Beta)

MWE-SECTOR-SWINGS-001 | Tool: Sector Rotation Tracker

The shared tracker now includes Suggested Swing Trades (Beta), after Event Log, on sector, Tech & AI, Stock Lookup and S&P 500 Top 50 pages. Anchor: `#suggested-swing-trades`. Suggestions are scoped to the current page's tradeable stock/ETF symbols; custom basket indices are excluded.

## Current scope

The user is still gathering entry rules. The server-only `swing-data.ts` adapter deliberately returns no suggestions. Production displays empty Active and Archive tables, with no invented candidates or reasoning. There is no entry form, recommendation engine, broker integration, new collection job, database table, or live suggestion persistence in this release. Once entry rules are supplied, connect the loader to durable recorded suggestions rather than continuously recomputing old signals. Do not embed private records in code or public client bundles.

Each suggestion requires a stable ID, symbol, suggestion date, Long/Short side, explicit entry price, and reasoning. Existing authenticated routes pass suggestions and a server-seeded New York market date to the client. The age/date refreshes while the page is open; daily prices refresh with page data.

## Tracking contract

- Day 0 is the suggestion date. Age counts Mon–Fri strictly afterward, including weekday market holidays. Weekends do not advance age; dates use America/New_York.
- Active includes Days 0–15. On Day 16, display in Archive, freeze displayed age at 16, and cap all price measurements at the Day 15 calendar date. Archive reasoning is retained. Later price bars do not change archived outcomes.
- Entry price is supplied explicitly. This version assumes suggestions are recorded at the daily close. Post-entry excursions therefore begin with the next daily bar, never the suggestion day's pre-entry high/low.
- MFA is maximum favorable advance. Long: max(0, highest post-entry high minus entry). Short: max(0, entry minus lowest post-entry low).
- MAE is maximum adverse excursion. Long: max(0, entry minus lowest post-entry low). Short: max(0, highest post-entry high minus entry).
- Both excursions show nonnegative dollar and percentage magnitudes. Current price is the latest available close through the active measurement date, or final close through Day 15 for Archive. Every price displays its as-of date.
- Price change and percentage change are raw current-minus-entry price moves, not side-adjusted P&L. Day 0 starts at entry and zero excursion. Later missing prices remain unavailable; valid closes may still display when OHLC is missing, with excursions marked unavailable/incomplete.
- All prices must use the same split-adjustment basis. Existing provider data excludes dividends, costs and fills.

Archive uses a fixed measurement horizon, not a separately materialized immutable snapshot. Provider corrections or revised historical data can restate the inputs. Durable suggestion and archive snapshot storage can be wired with the future entry logic; it is not claimed to exist now.

## Verification

60 Node checks and Next.js production build/typecheck pass. New tests cover Day 0, weekend/holiday counting, Day 15/16 boundaries, Long/Short MFA/MAE, exclusion of Day 0 highs/lows and future bars, missing/invalid/duplicate data, unchanged results from bars after the cutoff, empty production state, reasoning before rows, Archive and basket exclusion.

Browser fixture used clearly labeled synthetic entries/prices, verified empty state, Active reasoning and all nine columns, and visible Archive reasoning/final-price fields. No real suggestions were inserted. Signed-in production flow was not tested.

## Numbered methods

See [SWING_METHODS_V1.md](SWING_METHODS_V1.md). Suggestions now require `methodId` (1 or 2), displayed in reasoning and Active/Archive tables. Method #1 captures the user-supplied Sector rotation framework with precise thresholds pending; #2 is a researched RSI(2) trend-pullback draft. The signal loader remains empty pending complete rules and validation.
