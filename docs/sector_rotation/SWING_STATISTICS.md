# Swing play statistics and Method 1 inputs

Play statistics appears directly above Archive. Rows always show Longs, Shorts and Both for the current tracker symbol scope, including both Active and Archive records. The Open/Close selection determines the entry basis; the direction filter does not hide statistical groups. Each saved signal contributes once per selected basis; Both is a pooled per-play mean, not an average of the two group means.

Columns: Count, average MFE (dollars and entry-relative percent), average MAE (dollars and percent), average raw price change percent, average positive price change percent and average negative price change percent. Up/down excludes flat moves. Raw price signs match the suggestion table: price down can favor a Short. These are price-reference observations, not realized returns or side-adjusted P&L. Archived inputs use the existing Day 15 cap; active observations reflect latest available data and unequal ages.

Missing/nonfinite values are excluded, never replaced with zeros. Incomplete OHLC paths are excluded from MFE/MAE means. Pending entries remain in the total count; priced count and each metric's n make denominators explicit. Day 0 valid zero excursions and flat returns remain eligible in their applicable means. No signal generation, outcome optimization, new persistence or schema changes are involved.

75 Node checks and production build/typecheck passed. Tests verify pooling, Short raw return direction, flat/missing/incomplete data, empty groups and placement above Archive. Browser fixture verifies all groups remain visible under Longs-only and averages change with Open/Close.

## Method 1 clarification

User selected ETFs AND stocks and BOTH pullback and breakout setups. The user subsequently selected existing measures for Method 1 leadership. Official RRG will be researched for possible later implementation; this roadmap note is shown in the page’s Methods section. Exact leadership thresholds remain unapproved; no generator is activated by this choice.

Existing-measure implementation: define explicit relative-performance windows, momentum/change rules, ranks and/or EMA confirmation using current price history. Existing daily-return differences, RSI14 differences, Mansfield200 and daily ranks are distinct indicators; none is official RRG. A possible multi-week price-ratio screen would be a new explicitly specified rule using those prices, not an existing official RRG input.

Official RRG: JdK RS-Ratio measures relative trend and JdK RS-Momentum measures its momentum. Both normalize around 100. Leading: both above 100; Weakening: ratio above, momentum below; Lagging: both below; Improving: ratio below, momentum above. Requires identifying an actual source of official inputs, which current tracker storage does not contain. Choose daily/weekly timeframe and exact transitions; RRG itself does not supply a complete trade plan.

Primary reference checked October 26, 2026: https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-types/relative-rotation-graphs-rrg-charts

Existing measures are recommended for implementation simplicity/auditability, not claimed trading superiority. Remaining choices include leadership rules and thresholds, stock-to-sector mapping and candidate ranking, market confirmation, exact pullback and breakout triggers, permitted Long/Short directions, repeat-signal behavior, and stops/exits. The current next-open reference and Day 15 tracking horizon are display assumptions, not a complete execution or exit strategy.
