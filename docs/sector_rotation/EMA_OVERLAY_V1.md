# Selectable 20 EMA price overlay
Thread: Tool: Sector Rotation Tracker
MWE: MWE-SECTOR-EMA-001 (E1, ZERO_INCREMENTAL_COST_FIRST)

Daily price history now has a Chart line dropdown: None or 20 EMA. The default
is 20 EMA, drawn in blue with the selected session's EMA value beside the control.
The options list is ready to extend with future overlays. Applies to ETF candles
and basket closing-index charts; units follow the underlying price or index.

Calculate on full loaded Session history before slicing the visible window.
Use alpha=2/21 and the arithmetic mean of the first 20 consecutive valid closing
prices as the seed. No EMA is displayed before the twentieth close. A missing,
nonfinite or nonpositive close resets both the EMA and 20-session warmup; no
future prices or filled observations are used. This seed convention is explicit
and is not claimed as exact parity with another platform's initialization.
The price axis includes enabled EMA values so the line stays within the plot.
Existing chart geometry and linked scrolling remain shared and unchanged.

Verification: 41 model/render checks and Next.js build/typecheck passed.
Browser fixture with actual Tracker, components, hook and CSS verified default
line presence, None hides it, reselecting restores it, and switching Last 60 to
Last 20 retains the selected EMA value while showing 20 candles. Synthetic
prices are used only in the temporary QA fixture, not the production app.
Signed-in production interactions remain outside fixture coverage.
