# Numbered swing methods

## Implemented scope

Suggested Swing Trades (Beta) now contains a numbered Methods list. Method 1 is Sector rotation, based on the user-supplied framework and labeled Rules draft. Method 2 is the researched RSI(2) trend-pullback proposal, explicitly labeled Research draft. Active and Archive tables have a Method column, and reasoning cards carry the same method number/name.

Every suggestion must supply `methodId: 1 | 2`. The tracking engine rejects missing or unknown IDs rather than guessing attribution. IDs survive the Day 16 archive transition. Separate suggestions for the same symbol under different methods remain separate records, keyed by their recorded suggestion IDs. Existing Day 0, weekday age, Day 15 horizon and excursion behavior are unchanged. No real recorded suggestions currently exist; the server loader remains empty.

## Method 1: user-supplied Sector rotation framework

Screen the 11 major sector ETFs against SPY over a multi-week horizon. Seek sectors transitioning from Improving to Leading or pullbacks within established leadership. Candidates can be a sector ETF itself or the top 2–3 stocks inside a leading sector, with a bull-flag/base breakout or moving-average support setup. Require compatible broad-market context, with business-cycle alignment as contextual input.

Unspecified details remain explicit: daily versus weekly evaluation, multi-week lookback, numerical leadership/rank cutoffs, transition and pullback definitions, stock-strength ranking and sector mapping, market-distribution filter, business-cycle data, and risk/exit rules. No numerical thresholds, macro classifications or individual-stock mappings are guessed.

RRG uses JdK RS-Ratio and RS-Momentum; existing Mansfield RS, RSI comparison and daily rank are different measures. Do not label a proxy as official RRG or silently substitute one. QQQ tracks the Nasdaq-100 across sectors and is not one of the 11 sector SPDRs. ETFs reduce single-stock concentration but retain market, sector and constituent headline risks.

Primary references checked:
- https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-types/relative-rotation-graphs-rrg-charts
- https://www.ssga.com/us/en/intermediary/capabilities/equities/sector-investing/select-sector-etfs
- https://www.invesco.com/us/en/financial-products/etfs/invesco-qqq-trust-series-1.html

## Research proposal for method 2

The hypothesis is that an extreme short-term move against an established trend may revert. Draft daily setup conditions are:

- Long: split-adjusted close above its 200-session simple moving average, and Wilder RSI(2) strictly below 5.
- Short: close below its 200-session simple moving average, and Wilder RSI(2) strictly above 95.

These draft thresholds are fixed here before any strategy outcomes are examined. RSI(2) is distinct from the heatmap's RSI(14) versus SPY measure. The draft is inspired by the Connors RSI(2) approach described in StockCharts' own strategy documentation. Connors Research's 2012 presentation independently documents short-period RSI pullback research, but covers leveraged ETFs with different entry rules; it is background, not validation of this stock/ETF proposal.

Sources read October 26, 2026:
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2
- https://cmtassociation.org/wp-content/uploads/2024/01/0808-connors-1.pdf

There is no demonstrated performance claim for the tracked universe. No strategy backtest, parameter search, protected outcome inspection, signal generator, paid data change, additional collection job or activation occurs in this release. This draft supplies a concrete idea for subsequent specification and testing.

## Next implementation inputs

Method 1 has a qualitative framework; exact measurable conditions are still needed. Before either generator is activated, specify the exact universe, signal versus entry timestamps, entry reference or fill model, repeated-signal behavior, exits and risk rules, missing-data eligibility, and versioned persistence. The current overnight feed cannot produce an executable fill at the prior closing price after that close is known. The tracker currently uses a recorded close reference; any executable-entry model must explicitly address that timing.

Archive at Day 16 is a tracking horizon, not an instruction to exit a position. Source strategy exit rules must not silently override that contract. Preserve existing frozen strategy protocols separately; this UI draft does not modify or certify them.

## Verification

68 Node checks and a clean Next.js production build/typecheck passed. After the user supplied Method 1 during deployment, its draft name/description and expectations were updated and the same 68 checks passed again; tracker calculations were unchanged. The first build encountered a stale local Turbopack persistence cache; moving the generated cache aside and rebuilding succeeded without source changes. Browser QA used clearly labeled synthetic records to verify both methods in the numbered list, reasoning cards, Active table and expanded Archive. Synthetic records are absent from production sources. No authenticated production data access was bypassed.
