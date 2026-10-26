# Heatmap and detail chart date synchronization

Thread: Tool: Sector Rotation Tracker

The detail chart consumes the entire filtered heatmap session list, reversed
into the same newest-first order. It no longer truncates to 20 sessions.
Session count, From/To filters and Reset therefore affect both views together.
Each bar has a date/year label. A shared scrolling container keeps bars and
date labels aligned and readable for 120-session and all-history views.

The averages retain their existing prior-60-session baseline relative to the
selected date. Visible range filters do not redefine that statistical baseline.

Validation: four render checks passed, including a full Tracker comparison of
all 60 default heatmap dates against chart dates and a 120-bar chart. Production
build required before release. Signed-in browser interaction remains unverified.
This supersedes previous documentation describing a last-20-session chart.
