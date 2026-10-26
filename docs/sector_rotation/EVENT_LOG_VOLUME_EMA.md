# EMA 50, volume and Event Log

MWE-SECTOR-EVENTS-001 | Tool: Sector Rotation Tracker

All shared tracker pages inherit these changes: sector ETFs, Tech & AI, single-stock lookup, and the S&P 500 Top 50 constituents.

The heatmap Chart line selector offers None, 20 EMA (default), and 50 EMA. It controls the price overlay and 20E/50E markers together. Each EMA uses a period-matched SMA seed and alpha 2/(period+1), full loaded history, and restarts after a missing close. Strict close-below comparison; equality is not a marker.

Daily OHLC charts include a volume panel beneath candles, sharing the same SVG date axis, bar widths, and linked horizontal scroll. The amber overlay follows Sessions: trailing 20/60/120-session simple average including the current day, or an expanding average through each historical day for All available. The average uses pre-window history, breaks on missing volume, and retains zero volume. Basket indices have no invented aggregate volume.

Event Log uses the heatmap date range and measure, newest first, with alternating day shading. Each day expands to four sections. Only the expanded body mounts to keep the 51-stock page compact. Symbol buttons select the stock and event date in existing details/charts.

- EMA events match visible superscripts exactly. First day and Day N in a row count through that close, using loaded history; absent markers or missing metric values reset the run. None disables this section. Each entry appends the symbol's average completed below-EMA streak length within the Sessions window ending that day, plus sample count. Only fully observed completed runs contained in the window qualify; the current run, truncated runs and unknown/missing boundaries are excluded. N/A means no eligible completed run. All available uses history through that date.
- Beyond-average events are grouped under Long and Short headings. They use prior 60 sessions, excluding today, requiring 60 valid metric values and at least five same-direction samples. Positive/negative returns, relative returns and rank changes compare to their corresponding signed mean. Strictly beyond the mean creates Long/Short context. Rank compares to the prior 60-session overall mean, with lower numerical rank as Long and higher as Short. Labels are descriptive observations.
- Current Longest Streaks lists only the longest active green and red runs across the displayed symbols, including all ties, for every measure (relative, daily, rank, rank change), independently of the selected heatmap measure. Runs include the ending day and use full loaded history. Each color is N/A unless its longest current run exceeds one session. Missing or flat values break runs. Rank uses better/worse than the universe midpoint; other metrics use positive/negative values. Single-stock rank comparisons remain N/A.
- Biggest rank gain/drop uses all tied extrema in rankChange, with complete comparisons required. Single-stock pages omit this comparison.

Events are derived from verified loaded daily observations, not a separate stored audit journal. Provider corrections can therefore revise historical events. New daily collections appear on refresh. There are no new provider requests, tables, scheduled jobs, access policies or dependencies.

Validation: 51 Node checks including full-history 50 EMA, volume warmup/zeros/gaps, no-lookahead averages and streak records, tied rank movers, and date-section rendering. Next.js production build/typecheck passed. Browser fixture uses synthetic values and verified all 51 rows, 50E/overlay switching, None, 60 aligned volume bars, average-volume line, alternating shades, historical day expansion, metric changes and event-symbol selection. Signed-in production QA is not performed.

## Session/streak refinement — MWE-SECTOR-EVENTS-002

Sessions is passed explicitly from Tracker to volume and Event Log; values are 20, 60, 120 or all. Custom date filtering retains full-history baselines. Volume gaps reset average warmup for numeric and expanding windows. Beyond-average metric baselines remain the prior 60 sessions as before; the requested session-duration change applies to volume and EMA streak averages.

Validation: 55 Node tests and Next.js build/typecheck pass. Added checks for numeric and expanding volume means, no future contamination, completed EMA run boundaries and changing window lengths, all-measure current winners/ties/N/A, and grouped Long/Short rendering. Browser fixture verified all Sessions options, changing EMA means, independent all-measure winners, and N/A on a day with no run over one. Signed-in production browser flow remains untested.
