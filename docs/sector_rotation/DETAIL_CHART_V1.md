# Sector detail layout and relative performance averages

Thread: Tool: Sector Rotation Tracker

Sector Detail now follows the heatmap in a single-column workspace at every
viewport width, with static positioning. Applies to main sectors and Tech & AI.

The relative daily performance chart adds a green dashed positive-move mean
and a red dashed negative-move mean, with numeric labels and sample counts.
Both use sector/group daily return minus SPY daily return, in percentage points.
These differ from the existing absolute price-return directional averages.

For the selected date, take the 60 reference sessions strictly before it from
full loaded history. Average positive and negative relative returns separately;
exclude flat days. Draw each line only with 60 complete prior relative returns
and at least five observations of its sign. Missing history is labeled; no
price-return fallback is used. Date selection recalculates both lines; filtering
the visible heatmap does not change the baseline for an unchanged selected date.
Bars remain the last 20 visible sessions. All bars and lines use one symmetric
linear scale with headroom, without clipping large values. Date labels,
keyboard-accessible bar selection and numeric legend accompany the colors.

Validation: 22 model checks, including independent price/relative direction and
selected/future exclusion plus missing-relative behavior. Production build and
server-render checks are run before release. Signed-in browser interaction
verification remains unavailable without an authenticated MULtipLY session.
No collector, research methodology, constituents or external dependencies change.
