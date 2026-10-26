# Shared EMA control
Thread: Tool: Sector Rotation Tracker
MWE: MWE-SECTOR-SHARED-EMA-001

Chart line dropdown moved to heatmap filters beside Measure. Single Tracker
state defaults to 20 EMA and controls historical 20E superscripts and the daily
chart EMA overlay together. None hides both, their marker tooltips and the EMA
legend. The chart retains its read-only selected EMA value when enabled, with
no separate dropdown. Options live in chart-lines.ts for future extension.
EMA calculation, date windows, price column and linked scrolling are unchanged.

All 42 model/render checks and production build/typecheck passed. Browser fixture
with actual Tracker verified one dropdown in heatmap controls: default 660
markers and one line, None zero markers and zero lines, restored 20 EMA 660
markers and one line. Uses synthetic declining prices. Signed-in production
interactions remain unverified.
