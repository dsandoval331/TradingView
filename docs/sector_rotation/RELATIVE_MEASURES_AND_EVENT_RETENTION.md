# Relative measures and rolling Event Log

## Behavior

The Measures dropdown supports RSI (14) versus SPY RSI and Mansfield Relative Strength on sector, Tech & AI, Top 50 and single-stock trackers. The selected measure drives heatmap cells, session details and the synchronized performance chart. Both indicators also participate in Beyond average and Current Longest Streaks in the Event Log. CSV exports include raw symbol RSI, SPY RSI, RSI difference and Mansfield RS.

RSI uses Wilder's 14-session smoothing: initialize average gains and losses with 14 changes, then update each average with `(previous * 13 + current) / 14`. RSI is `100 - 100 / (1 + averageGain / averageLoss)`. The comparison is symbol RSI minus SPY RSI, in RSI points. Only gains yields 100, only losses yields 0, and a completely flat series yields 50. Values need 15 consecutive valid closes; a missing or invalid close resets initialization.

Daily Mansfield RS is `100 * (ratio / SMA(ratio, 200) - 1)`, where ratio is symbol close divided by SPY close. The current session is included in its 200-session average. This is the daily 200-session variant, rather than the classic weekly 52-period variant. Missing either paired close resets the window. Positive values mean the price ratio is above its own average; negative values mean it is below. Values are withheld until 200 consecutive paired observations exist.

Indicators use all loaded history before the Sessions or date display filters apply. Neither uses future observations. Existing collector history is retained for warmup and other calculations; no fabricated indicator values are displayed when history is insufficient.

The Event Log is derived from price history rather than persisted in an accumulating event table. It displays the newest 120 trading-day entries matching the heatmap date filters, newest first. A new day displaces the oldest displayed day at the cap. Shorter display windows show fewer entries. Price history is not deleted.

## Daily collection timing

Existing GitHub Actions schedules remain unchanged. All times below are UTC, Tuesday through Saturday, collecting the prior Eastern-calendar day:

| Universe | First scheduled run | Retry |
| --- | --- | --- |
| Sectors | 06:15 | 10:15 |
| Tech & AI | 07:15 | 11:15 |
| Stocks / Top 50 | 08:15 | 12:15 |

During Central daylight time these first runs are 1:15, 2:15 and 3:15 AM CT; retries are four hours later. During Central standard time they occur one hour earlier. GitHub scheduling and the shared collector concurrency group can delay actual start times. The tracker displays newly collected observations after loading the refreshed data.

Massive Stocks Basic makes daily bars available after midnight ET and denies current Eastern-calendar-day queries even after market close. A current-day entitlement would be required for a useful market-close collector. No paid plan, additional scheduler or collector date-bound change is introduced here.

Sources checked October 26, 2026:
- https://massive.com/knowledge-base/article/on-the-free-basic-plan-when-can-i-pull-the-previous-trading-days-data
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-strength-index-rsi
- https://trendspider.com/blog/new-indicators-added-dorsey-and-mansfield-relative-strength/
- https://charts.trendspider.com/shared/65f9160131c81e000982a415

## Validation

- Node sector-rotation suite: 67 passing tests, including hand-calculated indicators, warmup/gap resets, no lookahead, CSV exports, rolling retention and all six Event Log measures.
- Next.js production build and TypeScript validation passed.
- Browser QA with a clearly labeled synthetic 300-day / 51-symbol fixture: both options selectable, indicator detail values rendered, chart units correct, and All available retained exactly 120 Event Log days.
- Authenticated production data flow is not bypassed for browser QA.
