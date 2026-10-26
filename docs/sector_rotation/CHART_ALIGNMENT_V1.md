# Aligned chart dates and linked horizontal scrolling
Thread: Tool: Sector Rotation Tracker
MWE: MWE-SECTOR-ALIGN-001 (E1, ZERO_INCREMENTAL_COST_FIRST)

Performance history now runs oldest to newest, matching daily price history.
The heatmap keeps its existing newest-first layout. Both charts use the same
filtered sessions, a shared 72px left gutter and 20px right gutter, and identical
session slots (24px for longer windows, shared minimum 720px content width).
Performance bar bodies have the same width and center as candle bodies. Date
labels use the same spacing in both plots. Missing observations retain slots.

Both scroll containers share absolute pixel scroll offsets in both directions.
The handler avoids writing an unchanged offset. ResizeObserver realigns/clamps
the common scroll range after resizing or session/group changes. Selection and
all four performance measures retain their established semantics. No data,
collector, access-control, or research calculation change.

Verification: 37 Node model/render tests and Next.js build/typecheck passed.
A browser fixture bundles the actual Tracker/components/CSS/hook with explicitly
synthetic data. Browser checks passed on 20-, 60-, and 150-session windows,
including relative/daily/rank measures, exact date sequences, equal column
centers and slot/body widths, bidirectional scrolling, right-edge clamping,
and resizing between 640px and 1000px containers. Signed-in production data
interactions are not covered by this fixture.
