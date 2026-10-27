# Method 3 — Volume and SPY-relative confirmation

User-defined screen added October 27, 2026. Uses the displayed tracker’s tradable stocks/ETFs, excluding synthetic baskets. It calculates retrospective matches from October 6, 2026, the initial tracker suggestion lookback date, from existing published price history. No new data source, database writes or scheduled recording job.

## Exact rules

All three conditions must hold on the same completed daily bar:

| Condition | Long | Short |
| --- | --- | --- |
| Volume | Strictly above Sessions average | Strictly above Sessions average |
| Daily close change | Close > prior session close | Close < prior session close |
| Relative to SPY | Daily return − SPY daily return ≥ +0.05 pp | Daily return − SPY daily return ≤ −0.05 pp |

Green close means positive close-to-close daily return, consistent with the price column. It does not mean close above that day’s open. Relative confirmation matches the heatmap’s actual green/red colors, using its shared 0.05 pp neutral threshold. Relative to SPY is the existing daily return difference in percentage points; it is independent of the currently selected heatmap measure. No EMA, RSI, sector leadership, ranking or additional market filter applies.

Volume reuses the chart’s trailing arithmetic average, including the signal session. Heatmap Sessions selects 20, 60, 120 or All available, default 60. Fixed periods require a full consecutive window of valid nonnegative volumes; missing/negative/nonfinite volumes reset the window. All uses valid contiguous history through each signal day, resetting after missing volume. Zero volume is valid. Flat price changes, neutral relative returns (absolute difference < 0.05 pp), equal volume and unavailable comparisons do not qualify.

SPY published session dates provide the calendar. Return calculations reuse the heatmap implementation and do not bridge missing symbol sessions. Future bars beyond the page’s as-of date are excluded. Every qualifying session is a separate signal. Consecutive repeat counts include qualifying history before the display start, reset on any lost condition/data gap and restart on a direction change.

## Tracking and comparison

Method 3 uses signal close as its stored reference within the calculated result. Existing Open/Close views, pending next-session open handling, weekday Day 0/15/16 lifecycle, excursion definitions and frozen Day 15 measurement horizon apply. It appears in Active, Archive, reasoning, method filters, separate method statistics and pooled All methods statistics. Longs and Open remain default. All methods replaces the former Both label now that there are three methods. A symbol/date qualifying under multiple methods contributes separately per method.

Results are calculated at page load and when Sessions changes. They are not immutable recorded snapshots; membership, historical data and Sessions changes can restate calculated Archive. Method 2 saved entries and Method 1 settings are unchanged. Current trade reasoning remains visible only for the page’s current market date; older reasoning remains expandable. This screen is not a validated strategy or an execution/exit system.

## Verification

Synthetic tests cover Long/Short rules, volume and return equalities, mismatched price/relative signs, missing data, warmup and Sessions alternatives, future exclusion, repeat boundaries, basket exclusion, duplicate rejection, Open/Close tracking, Archive, method filters and separate/pooled statistics. Production build/typecheck and browser checks validate integration. No thresholds were tuned to observed market outcomes.
