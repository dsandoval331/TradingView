# Method 2 recent retrospective matches

MWE-SECTOR-METHOD2-BACKFILL-001 | Tool: Sector Rotation Tracker

## Recorded population

At the user's request, screen existing tracker prices as of October 26, 2026 for Method #2 matches strictly under 15 weekdays old. Result: 63 symbol-day entries across 27 symbols, comprising 33 Long and 30 Short matches dated October 6–23. The Top 50 tracker displays 51 of these entries, the sector tracker 11, and one additional entry belongs to a separately tracked stock. Each page retains its existing symbol scope.

Rules are fixed as `rsi2-sma200-v1`: Long when close is strictly above its SMA200 and Wilder RSI(2) is strictly below 5; Short when close is strictly below SMA200 and RSI(2) is strictly above 95. Equal thresholds do not qualify. Each matching symbol/date/side is separate, including consecutive days; no outcome or return filter is applied.

Use all available history through the as-of date for initialization. The 200-session average includes the signal day. Wilder RSI uses the same tested implementation as the heatmap, with period 2 and a two-change SMA seed; flat gains/losses are neutral 50. SPY observation dates provide the market-session calendar. Missing/invalid symbol closes reset RSI and SMA warmup. SPY and synthetic theme baskets are excluded as suggestions.

Read 32,356 published price rows for SPY and 64 tracked instruments from existing stock/sector views plus the IGV ETF in the tech view. No protected research population, macro labels, external paid data or new provider collection was used. Latest available close was October 23; no October 26 closing bar was fabricated.

## Persistence and display

`public.sector_swing_suggestions` stores stable IDs, version, signal date, side, reference close, reasoning, retrospective origin, actual recording timestamp and raw indicator snapshot metadata. Insertions use conflict-do-nothing. Initial insert recorded 63; an identical replay inserted zero. Underlying price history and existing research records were not altered.

Authenticated allowlisted users have read access through the existing allowlist function; anon has no read permission and clients have no insert/update/delete permission. The service role has select/insert only. SQL definition: `sql/sector_rotation/swing_suggestions_v1.sql`. The migration was applied before application publication. The loader pages through recorded snapshots and reports read failures rather than showing a false empty result.

Tables and reasoning cards sort newest signal date first, then symbol and stable ID. Rows are labeled Retrospective match with the actual added date. The entry price is a historical closing reference, not an executable fill. MFA/MAE begin with the next daily bar. Existing price updates, weekday age and archive rules remain: initial inclusion is Day 0–14, saved entries remain Active on Day 15 and archive on Day 16 with the price horizon capped at Day 15. Later price corrections can still restate excursion inputs under the existing tracking model.

This is a one-time backfill. Page loads read saved records; they do not regenerate or remove them as the lookback moves. No automatic daily signal job or executable entry/exit model is activated.

## Reproduction and checks

`scripts/sector_rotation/backfill_method_two.cjs` accepts explicit JSON on stdin: `{asOfDate,series:[{symbol,prices:[[date,close],...]}]}`. It runs the pure `method-two.ts` screen and emits candidate snapshots. It has no database credentials or network/write behavior. Keep raw observations and actual suggestion records out of source/client fixture bundles. Insert reviewed results through an authorized server-side data path, preserving their version and provenance.

71 Node checks pass, covering strict thresholds, 200-session warmup, missing-data reset, no lookahead, Day 14 inclusion / Day 15 exclusion, repeated daily matches, stable IDs, newest-first display, loader pagination and errors. Next.js production build/typecheck passed. Independent database verification matched all 63 entry closes and SMA200 values to published prices, and confirmed every initial age below 15. RLS/role grants and security advisors were checked; no advisor finding references the new table. Browser QA used labeled synthetic records and verified newest-first Day 1/Day 14 rows and retrospective labels; no authenticated production access was bypassed.
