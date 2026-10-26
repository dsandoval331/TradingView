# Heatmap price and EMA context
Thread: Tool: Sector Rotation Tracker
MWE: MWE-SECTOR-PRICE-001

Price column between ETF/Group and newest date shows the latest loaded market
session close and close-to-close daily return, independent of date filters and
heatmap measure. Its header states the latest session date. Missing prices/returns
remain unavailable. ETF values use dollars; custom baskets use labeled index
points. The column stays beside the group labels during horizontal scrolling.

Each historical cell adds superscript 20E when that session has a valid close
strictly below its own 20-session EMA, computed on full loaded history using the
existing chart calculation. Missing/unwarmed EMA or missing metric cells are not
marked; equality is not marked. Markers work for all four measures and both views.
Tooltip and accessible cell label explain the marker. Closing prices are split
adjusted, not total-return prices. Existing data and calculation contracts remain.

Validation: focused rendering checks cover column placement, latest close and
percent, expected historical markers, EMA warmup, and no marks at equality.
Existing model/render suite and production Next.js build/typecheck pass.
Authenticated production browser interactions remain unverified.
