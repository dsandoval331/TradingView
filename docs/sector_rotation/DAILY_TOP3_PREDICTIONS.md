# Predicting Daily Top 3 Sectors

Main sector page only, separate from historical winner combinations and the existing Top1 pattern suggestion. Each XLE, XLV, XLK forecast independently targets final daily close-to-previous-close rank against all eleven sector ETFs. Top3=1–3, Middle=4–8, Bottom3=9–11. Rank descending unrounded daily return, exact ties ticker ascending (ordinal ranks). No positive/green requirement; no EMA/streak gate.

## Prediction lifecycle

`public.sector_top3_predictions` stores one row per target_date/stage/symbol. Stages overnight/premarket/open30 preserve the original probabilities, reasoning, source URLs/timestamps, input cutoff, evidence confidence and database recording timestamp. Probabilities sum100; judgment-v1 is explicitly uncalibrated. availability=baseline_only labels insufficient current data. No retrospective fills, browser inserts, application updates/deletes, or application recording-time override.

Initial Oct28 overnight outlook is the actual conversation judgment (XLE25/35/40, XLV30/45/25, XLK50/35/15), saved Oct28 with its actual database timestamp and earlier input cutoff. It is not a new quantitative model or a premarket tape reading. No forecast exists for Oct27; show that explicitly rather than reconstructing one after results.

Existing ChatGPT research tasks are updated to weekday checks at08:25America/Chicago (premarket, task6ae18452c4a88191a80eaa2dd6602bbc) and09:00 (open30, task6ae1845ad814819194dac648784cdadf), starting2026-10-28. They research all11, check exchange holidays, report uncertainty/data delays, and insert the three completed rows atomically through authorized Supabase tools with ON CONFLICT DO NOTHING, then read back. No new paid feed or broker integration. These are research-task writes, not the GitHub nightly pattern model. If research fails or is late, report missing record; do not fabricate one. A schedule does not guarantee fresh quote availability or completion before cutoff.

DB checks require same New York target/record date, weekdays, data_as_of<=recorded_at, premarket/overnight before09:30ET; open30 recording10:00–11:00ET with input cutoff<=10:00ET. Actual issue times remain visible; open30 is not falsely timestamped exactly10:00. Automation prompts restrict premarket input to08:25CT and open30 input to09:00CT; service_role cannot override recorded_at. Holiday/calendar validation is in research tasks, not a SQL holiday calendar.

## Outcomes

`top_three.py` runs in the existing sector daily workflow after successful verified price collection, even if the older Top1 forecast step fails. Existing06:15/10:15UTC Tue–Sat schedule retained. It makes no market-provider calls. Reads published sector daily prices and COMPLETE collection boundary. For each forecast date lacking results, require exact target date, all11 valid daily comparisons plus SPY and time>=16:00ET. Missing date/comparison defers rather than jumping forward. Negative and flat days remain ranked. Results are inserted once in `sector_top3_results`; revisions/retries never restate them. Payload contains all11 ranks, returns/buckets, ranking definition and a price-derived hash. Source returns require adjacent published dates; missing sector prices prevent settlement.

UI compares each snapshot to those appended ranks, shows actual Top3 yes/no and whether actual category was among highest assigned probabilities (ties explicit). This categorical comparison is descriptive; a single event cannot validate or invalidate a probability. No performance-accuracy claim or profit inference.

Results appear after the next successful overnight refresh, not at market close. Early-close days are conservatively settled only after16:00ET or the overnight refresh. Failed collection blocks settlement. Main page server loader checks auth + existing allowlist, paginates predictions/results separately with stable ordering and reports read errors rather than empty history. Tables use RLS allowlisted authenticated SELECT, no anon read; service_role SELECT and column-specific INSERT only. SQL administrative tooling remains privileged and is instructed never to backdate/overwrite.

## Display

Today and yesterday (New York calendar dates) expanded, including honest no-record states. Earlier recorded days collapsed independently. Latest recorded stage displayed, older same-day stages available under a collapsed disclosure. All three ETFs shown independently; absent ETF remains no-record, not0%. Source links permit HTTPS only. Section independent of heatmap Sessions, TopN and date filters. Refresh page to see new recorded checks/outcomes; no live polling.

## Verification

22Python tests,101Node tests and production Next build/typecheck passed. New tests cover negative-day Top3, exact-date/future independence, missing prices, deterministic ties, retry idempotency, mocked full settlement flow, auth/read errors, current/yesterday/older expansion, pending/completed original snapshots and URL filtering. Database checks verify RLS/privileges, no timestamp override, no unauthorized rows, rejection of invalid probability sums/early open30/backfills/early results. Browser fixture verifies layout/disclosures and synthetic result analysis. Live scheduled research and first true closing settlement remain pending until their respective times.
