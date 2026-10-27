# Method 1 configurable sector-rotation screen

MWE-SECTOR-METHOD1-001 | Tool: Sector Rotation Tracker

## Approved defaults

The user approved configurable choices with these defaults: ETFs and stocks; all tracked stocks; both Longs and Shorts; both pullback and breakout setups; combined relative and Mansfield sector leadership; top 3 qualifying stocks per sector and direction; 20-session stock/sector ratio performance, 5-session ratio tie-break then ticker; signals every qualifying session with consecutive-repeat labeling.

Leadership defaults to sector/SPY price-ratio performance above zero over 20 sessions and above zero over the last 5 sessions, plus daily Mansfield(200) above zero and higher than 5 sessions ago. Shorts invert all signs. Mansfield uses `100 * (current ratio / SMA(ratio, period) - 1)`, including the current session. Relative-only, Mansfield-only and Both are configurable.

Pullback default: the previous close is at/below its previous EMA20 and the current close crosses above its current EMA20 for Longs; reverse comparisons for Shorts. Slow EMA50 and either EMA are alternatives. Breakout default: close strictly exceeds the maximum high of the prior 20 sessions for Longs, or falls below their minimum low for Shorts. Today's high/low is excluded from its breakout range. SPY defaults to close > EMA20 > EMA50 for Longs and the inverse for Shorts; slow-EMA-only or no filter are alternatives.

The server scans the complete published stock universe and sector ETF histories, independent of the current tracker page. After sector, market and instrument-setup qualification, rank stocks within each sector/direction. Longs sort relative scores descending; Shorts ascending. Ties use the short-period score, then ticker, at unrounded precision. Top N is a maximum, never a quota. A stock qualifying for both setups gets one row per setup but occupies one stock-selection slot. Sector ETFs qualify directly and do not consume stock slots. Mansfield and short-period ratio rankings are alternatives; Mansfield stock ranking uses its sector ETF as the benchmark.

## Controls and calculation semantics

Expand Method #1 settings. Settings are validated on client and server, then applied explicitly. The initial screen restores valid browser settings or approved defaults. Apply settings changes only Method #1 calculated results; Reset defaults recalculates with the defaults. Draft changes and last applied settings are identified. On errors the last successful result is retained. Browser-local storage is versioned and failure-safe.

All periods count SPY trading-session observations. Numeric periods are configurable from 1–260; fast EMA must be shorter than slow EMA; top N from 1–10. Dates are validated. Initial display starts October 6, 2026, matching the existing recent-screen starting range, and is configurable. History before that date initializes indicators and repeat counts. A request exceeding 5,000 calculated matches is rejected with a narrower-range instruction rather than silently truncating.

Repeat identity is symbol + Method 1 configuration/mapping version + side + setup. The observed streak increments only when the full signal, including rank selection, qualifies on consecutive SPY sessions. Missing data or any failed gate resets it; absent weekend/holiday sessions do not break it. First occurrence is 1 session; repeat at 3 means 3 consecutive qualifying sessions, or 2 repetitions after the first. Open/Close entry variants share the same signal metadata. First-only mode filters output without resetting the underlying streak.

Calculation IDs include fixed-order settings and the mapping version, date, symbol, side and setup. Existing Open/Close reference pricing, age, excursion and Day 15/16 archive horizon logic is reused. Price returns retain the existing raw sign. Stats include the selected entry basis for saved Method 2 and calculated Method 1 signals in the current page's symbol scope.

## Data, access and limits

This is a **calculated retrospective screen**, not a table of immutable contemporaneously recorded signals. Page load and Apply settings call an authenticated, allowlisted, read-only server action. It paginates the complete existing stock and sector daily views, with no privileged credentials or new RLS grants. No external provider collection, paid integration, trade execution, database migration or write to saved suggestions is introduced. Method 2 snapshots remain intact.

Changing settings, tracked membership, sector mappings or corrected source prices can restate calculated signals and their Archive. There is no durable Method 1 recording job, automated configuration optimization, stop/target execution or validated performance claim. The existing Day 15 measurement cap is a tracking horizon, not an exit rule. Official RRG remains future research, as noted on the page.

Sector mappings are curated current economic-sector proxies, not point-in-time index membership. The current 52 tracked stocks have mappings; unknown future symbols are reported and excluded, never automatically guessed. Mapping version: sector-proxies-2026-10-26. Current Top 50 selection uses the existing pinned constituent snapshot. Synthetic baskets are excluded as trades.

Mapping references include existing reviewed `holdings.json` issuer snapshots and primary State Street sector-fund pages, including:
- https://www.ssga.com/us/en/intermediary/etfs/state-street-technology-select-sector-spdr-etf-xlk
- https://www.ssga.com/us/en/intermediary/etfs/state-street-communication-services-select-sector-spdr-etf-xlc
- https://www.ssga.com/us/en/intermediary/etfs/state-street-financial-select-sector-spdr-etf-xlf
- https://www.ssga.com/us/en/intermediary/etfs/state-street-consumer-staples-select-sector-spdr-etf-xlp

Mappings beyond displayed issuer top holdings are curated sector proxies and are not represented as verified ETF membership. No frozen Swing Trades research datasets, protected validation populations, V4/V5 protocols or canonical research outcomes were opened or changed.

## Verification

81 Node checks pass. New tests cover combined leadership, Long/Short inversion, global top-3 ranking, universe selection, market gate, first-only repeats, repeat history before the displayed range, missing-session resets, pullback crossing, exclusion of today's breakout high/low, future-data exclusion, duplicate detection, configuration bounds/identity, deterministic ties, ETF-only scope, dual setups sharing slots, metadata in both entry variants, server authentication/allowlist rejection and positive read-only data flow/error handling. Next.js production build/typecheck passed.

A default-rule offline calculation on 31,857 authorized published tracker rows (52 stocks plus SPY and 11 sector ETFs) found 16 historical matches through October 23: 11 breakouts, 5 pullbacks, all Long under the default market gate, with 2 repeat-labeled rows. No thresholds were adjusted after inspecting this result. This verifies operation, not profitability. Raw prices and calculated records are kept out of committed source and browser fixture bundles.

Browser QA used labeled synthetic data and a simulated runner: approved defaults, repeat labels, stock-limit changes, saved Method 2 preservation, draft warnings, invalid EMA validation, reset defaults and non-default browser persistence after reload all verified. No production sign-in was bypassed. The real server action has unit coverage and the underlying published prices were read through the authorized connector; authenticated production browser flow was not independently exercised.

`scripts/sector_rotation/screen_method_one.cjs` reproduces the pure screen offline from explicit `{asOfDate,series:[{symbol,prices:[[date,close,open,high,low,volume],...]}],settings?}` JSON on stdin. It performs no network/database writes.
