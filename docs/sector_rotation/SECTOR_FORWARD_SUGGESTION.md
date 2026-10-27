# Next-session sector suggestion Beta — sector-next-v1

## Behavior

The main reverse-engineering section displays a permanently recorded Long sector pick for the next actual trading session, its pre-open timestamp, source session, source characteristics and historical pattern evidence. It later attaches a separately stored one-session result. No backdated predictions, broker orders, paid provider or new collection cadence. No stop/target/position sizing system.

The existing sector collector workflow runs at 06:15 and 10:15 UTC Tuesday–Saturday. The new forecast step runs only after that collection succeeds and its latest run is COMPLETE. It loads only the published sector daily view and the two new tracker-only snapshot tables. The free feed publishes completed sessions overnight. New picks are eligible only before 08:00 America/New_York, with source date before the current local date and at most four calendar days old. Source must equal the collector’s latest verified date and be complete. Delayed/manual daytime executions skip prediction creation; they may still settle old forecasts. A source-session/version unique key and serialized workflow retries make creation idempotent.

Actual target dates are not guessed from weekdays. The first next date in published SPY/sector observations resolves the target; any missing sector/benchmark comparison on that date defers settlement rather than jumping to a later date. A forecast must have been recorded strictly before that target date’s 09:30 ET opening time. This accommodates holidays/weekends when no observations are published; provider gaps remain unavailable.

## Fixed exploratory selection rules

One sector, Long only. Fixed Top 1 green historical outcome (daily close-to-close return ≥0.05%). Exact return ties use ticker order. The suggestion does not follow browser Top N, date filters or Sessions changes. Volume period is fixed at 60, EMA periods at 20/50. These rules were specified for this feature before any new forward outcomes; they are not validated and were not selected by backtest optimization.

Features use the close immediately preceding the labeled winning session: volume above its including-session 60-session average; positive daily return; positive daily relative return versus SPY; close above EMA20; close above EMA50; and positive daily-return streak ≥2. These are pre-session equivalents of characteristics already explored in the section. The daily streak is specifically daily-return, not the maximum of all six displayed metric streaks.

For every historical target session with all 11 sector daily returns and valid SPY return, label the canonical Top 1 green winner; if no sector is green, all labels are false. Train on up to the most recent 120 complete labeled sessions through the source close, requiring at least 60 labeled sessions. Each target’s feature vector comes from its preceding observed session; incomplete data remains unknown and never becomes a positive trait.

Enumerate distinct single, pair and triple patterns among the six fixed conditions (41 patterns). A pattern must match at the current source close, have ≥20 matching historical sector/date observations across ≥5 dates and ≥3 historical wins. Score is (wins+1)/(matching observations+2); baseline is (all historical winner labels+1)/(all training sector/date observations+2). Require score above that baseline. Rank patterns/candidates by score, then matching sample count, then fewer traits, then stable keys/ticker. Keep one candidate. If training or support is insufficient, store a no-pick entry instead of forcing a trade. Historical counts are descriptive; smoothing does not create a calibrated future win probability. Overlapping sector/date exposures and related conditions are not independent evidence.

## Recorded evidence and outcomes

The payload stores rule parameters, training first/last dates/count, selected symbol and pattern, all eligible candidates with source features, source bar SHA256 and git revision. One immutable-by-application-role row per version/source session is stored in sector_winner_forecasts. A version bump is required if model rules change; no update/delete privileges are granted to the recording role. No forecast is generated on browser page load.

The first complete next-session result stores canonical Top 1 green hit, competition rank, actual winner, daily return, relative pp, open, close, open-to-close percentage, and nonnegative high/open MFE and open/low MAE. Excursions require valid OHLC enclosing open/close; unavailable inputs stay null. They are one-session reference-price observations before costs, not realized P&L. Result snapshots are inserted once and not overwritten by later provider restatements. Predictions and results are never merged in a way that rewrites original reasons/features.

Both tables have RLS and authenticated SELECT only under the existing MULtipLY allowlist. Anon has no read access. The server recording role has SELECT/INSERT only, with no UPDATE/DELETE; browser roles cannot write. The server loader separately checks authentication/allowlist and reports read errors rather than presenting false empty history. Source rows have a pre-08:00 ET check; outcome rows cannot be recorded before target-day 16:00 ET. Schema is in the CLI-generated migration 20261027222141_sector_winner_forward_forecasts.sql.

## Verification and operational limits

Python tests verify prefix invariance, training support, duplicate rejection, missing data, pre-open/freshness guards, first-next-session settlement, missing-benchmark deferral, idempotent job retries and append-without-rewrite outcomes. Node tests cover authorization/error boundaries and pending/completed UI rendering. Database role/permission checks and a rolled-back linked snapshot/result insert verified persistence and unauthorized read denial. The new tables are absent from security-advisor findings; preexisting unrelated findings were not changed.

Initial deployment during daytime intentionally does not create a pick from an already stale session. The first eligible overnight collection is expected to populate the first forward record. Collection outages, stale/incomplete source data or jobs delayed past the cutoff can leave no new record. Existing job logs report forecast_created, results_appended, latest_source and preopen_window; failures fail the workflow without printing keys or provider bodies. Earlier dates are not invented as forward predictions. No automatic strategy promotion or model tuning is included.
