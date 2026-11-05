# TFM Friday selection review — exploratory

Thread: Tool: Sector Rotation Tracker
Analysis: TFM-EXPLORATORY-RANK-001
MWE: MWE-SECTOR-TFM-001 (19dd7129-0d19-4c1b-a65b-03480a925b8d)
Authority: E0 analysis; no production rule changes. ZERO_INCREMENTAL_COST_FIRST.

## Scope and outcomes

60 distinct stock symbols from the existing fixed Top 50 / Tech & AI union; ETFs excluded from stock selection research. Monday cases only. Historical study May 4–October 26, 2026: 655 qualifying stock-weeks, comprising 335 original Friday-low hits, 61 alternate successes, and 259 failures. A combined success is an original hit OR an original miss with target-open MFE >=0.5% and MFE/MAE >=2. Positive MFE with zero MAE qualifies; no double counting. Holiday Tuesdays are not pooled with Mondays. November 2 is an already-inspected diagnostic, not an untouched test.

## Method fixed before feature query

Bounded buckets were registered in Supabase event TFM_EXPLORATORY_RANK_PLAN_FIXED before examining feature rates. No threshold sweep. Development: through August 3 (328 instances over 11 ordinary Mondays); later consistency check: August 10–October 26 (327 instances over 11 ordinary Mondays). Both periods were already observed in prior research, so this is not independent validation. Stock-week counts are correlated. Per-week feature success rates were compared with all qualifying stocks that same week, and differences averaged equally across covered weeks. Supporting buckets require >=30 instances and >=5 weeks in each half. No p-value or independent-trial significance claims.

## Main findings

| Friday-known characteristic | Earlier combined rate | Later combined rate | Week-matched lift, early / later |
|---|---:|---:|---:|
| All qualifying stocks | 219/328 = 66.77% | 177/327 = 54.13% | Reference |
| Close in lower third of Friday range | 98/141 = 69.50% | 96/136 = 70.59% | +4.61 / +20.48 pp |
| Close within 0.5% of Friday low | 53/80 = 66.25% | 75/103 = 72.82% | +5.28 / +18.91 pp |
| Red Friday candle | 145/212 = 68.40% | 121/197 = 61.42% | +0.59 / +5.69 pp |
| Close above stock SMA50 | 122/178 = 68.54% | 82/140 = 58.57% | +3.93 / +4.83 pp |
| Close in upper third | 59/83 = 71.08% | 32/88 = 36.36% | -0.68 / -13.82 pp |
| Friday range >4% | 81/113 = 71.68% | 25/53 = 47.17% | +14.16 / -4.97 pp |

A large Friday gap down also reversed strength (70.95% earlier versus 43.52% later). Below SMA20 alone did not show stable week-matched improvement. Do not promote large selloffs, gaps, or a blanket below-SMA20 rule as reliable filters from this sample.

Original hits had average Friday close position 37.5% up the daily range; alternate successes 53.6%; failures 49.3%. Red Fridays occurred in 71.3% of original hits, 44.3% of alternate successes and 55.2% of failures. Alternate winners do not share the exact same profile as original hits; 61 historical alternate cases are too few for a dependable separate selection model here.

## Practical research shortlist

Prioritize the existing TFM setup when Friday close <= Friday low + (Friday high - Friday low)/3. Treat distance (Friday close - Friday low)/Friday close <=0.5% as supporting context, not a second independent point for essentially the same weak-close evidence. Red Friday and a close below Thursday close are weaker supporting characteristics. Above SMA50 offers modest consistent evidence but is not a mandatory exclusion rule. These are candidate ranking hypotheses; no score weights or hard production exclusions have been adopted.

## Latest-week diagnostic

For October 29–30 / November 2, the lower-third profile selected 16 stocks: 12 original successes and four failures (75%), versus 25/38 =65.79% combined for all qualifying stocks. Failures: GE, GEV, JPM, WFC. Successes: AMAT, ANET, BAC, CAT, CSCO, KLAC, META, ORCL, PLTR, QCOM, SNDK, WDC. This week was already inspected and must not be advertised as an unseen validation set.

## Execution sensitivity and limits

A lower Friday close mechanically makes a break of Friday low easier. Among lower-third cases, 55/277 opened below Friday low, versus 33/378 for other closes. Favorable full-session excursion quality (MFE>=0.5% AND ratio>=2, whether or not original target hit) occurred in 126/277=45.49% of lower-third cases versus 138/378=36.51% of others. This is a post-selection sensitivity diagnostic, not an optimized secondary strategy. A 70% combined hit rate is not a 70% profitable-trade rate. Daily bars cannot establish excursion order, fills, borrowing costs or realized P&L.

Fixed current membership introduces survivorship bias; GOOG and GOOGL are distinct share classes and correlated. SMA features use only closes through Friday, with 50-bar warmup and a same-adjustment close-parity guard. Current source histories are not a point-in-time corporate-actions archive. The breadth of exploratory comparisons increases false-discovery risk. Future Friday rankings should be logged before outcomes and retained alongside unfiltered candidates to test selection benefit prospectively.

## Provenance

Primary computation: existing Supabase Postgres, read-only analysis.sql, against immutable tfm_setups/tfm_outcomes and completed operational price views. Full bucket results and class/diagnostic tables in results.json. No new provider requests, paid resources, broker orders, or website changes. Research holdouts and other MULtipLY datasets were not used.
