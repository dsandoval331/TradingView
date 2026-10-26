# Numbered swing methods

## Implemented scope

Suggested Swing Trades (Beta) now contains a numbered Methods list. Method 1 is reserved for user-supplied rules. Method 2 is the researched RSI(2) trend-pullback proposal, explicitly labeled Research draft. Active and Archive tables have a Method column, and reasoning cards carry the same method number/name.

Every suggestion must supply `methodId: 1 | 2`. The tracking engine rejects missing or unknown IDs rather than guessing attribution. IDs survive the Day 16 archive transition. Separate suggestions for the same symbol under different methods remain separate records, keyed by their recorded suggestion IDs. Existing Day 0, weekday age, Day 15 horizon and excursion behavior are unchanged. No real recorded suggestions currently exist; the server loader remains empty.

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

Method 1 still requires the user's conditions. Before either generator is activated, specify the exact universe, signal versus entry timestamps, entry reference or fill model, repeated-signal behavior, exits and risk rules, missing-data eligibility, and versioned persistence. The current overnight feed cannot produce an executable fill at the prior closing price after that close is known. The tracker currently uses a recorded close reference; any executable-entry model must explicitly address that timing.

Archive at Day 16 is a tracking horizon, not an instruction to exit a position. Source strategy exit rules must not silently override that contract. Preserve existing frozen strategy protocols separately; this UI draft does not modify or certify them.

## Verification

68 Node checks and a clean Next.js production build/typecheck passed. The first build encountered a stale local Turbopack persistence cache; moving the generated cache aside and rebuilding succeeded without source changes. Browser QA used clearly labeled synthetic records to verify both methods in the numbered list, reasoning cards, Active table and expanded Archive. Synthetic records are absent from production sources. No authenticated production data access was bypassed.
