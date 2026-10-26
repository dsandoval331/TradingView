# Paired swing entry references

MWE-SECTOR-ENTRY-COMPARISON-001 | Tool: Sector Rotation Tracker

Every saved suggestion produces two adjacent table rows, ordered newest signal first: Signal close followed by Next session open. A separate Strategy column identifies Long or Short. Method, reasoning, suggestion date, weekday age, current closing price and archive horizon are shared. Reasoning remains one card per signal; Active/Archive counts count comparison rows.

The Signal close row preserves its recorded reference price. The Next session open row uses the first SPY market-session date after the signal, bounded by the measurement horizon, then the symbol's opening price on exactly that date. Weekends and market holidays without sessions are skipped. Missing, zero or invalid opens remain pending; a later symbol bar is never substituted for a missing first-session open. Future bars are excluded.

For next-open rows, price change and percentage change use that open as their denominator/reference, and MFA/MAE include the opening session's high and low. Long and Short excursions retain their existing directional definitions. Signal-close rows exclude signal-day pre-entry highs/lows. Pending entries have unavailable changes and excursions; an available current close may still be shown.

Day 0 and weekday age remain anchored to the original suggestion, including for the next-open comparison. Active includes Day 15; Archive begins at Day 16. Both rows cap measurement inputs at Day 15 after the signal. Entries show their actual reference dates. Price change remains the raw current-minus-entry move rather than side-adjusted profit/loss.

Comparison rows are derived from existing stored signals and published bars; they are not independent new signals or duplicated database records. The 63 saved signals produce 126 rows across tracker scopes. At implementation, 62 next opens were available and one awaited a published next-session bar. No fees, slippage or executable-fill assumption is added. Provider historical corrections can restate bar-derived open references and excursions under the existing model.

Verification: 73 Node checks and production build/typecheck passed. Tests cover paired rows, explicit Strategy, one reasoning card per signal, Friday-to-Monday and holiday session handling, missing first opens without bridging, future-date exclusion, entry-day Long/Short excursions, unchanged age/current close, and frozen measurement horizon after archive. Browser QA used labeled synthetic Long/Short and pending fixtures; production data counts were independently checked via the authorized database connector. No authenticated production UI was bypassed.
