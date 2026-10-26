# Shared heatmap and detail measure

Thread: Tool: Sector Rotation Tracker

The heatmap Measure control is the single source of truth for the Sector Detail
headline, directional-average panel and history chart in both views. Default:
relative daily performance versus SPY. Other modes: daily price return (%),
daily rank and rank change (places). The Sector Detail dropdown is removed;
selecting a heatmap row/cell retains the ETF/group selection behavior.

Above the average legend, the chart shows the selected session value and highest
and lowest visible chart values. Rank mode labels the extrema best/worst and
interprets lower numeric rank as better. Bars, titles, labels, tooltips and units
follow the selected measure. Rank-change values preserve arrows and places.

Return modes use the existing earlier-only 60-session signed means in matching
units. Rank modes suppress the return-average panel and lines; ranks are not
price returns. Rank bars rise from zero at the bottom, with #1 explicitly labeled
strongest. Rank changes retain their signed zero-centered scale. Supporting
facts, holdings and other named detail statistics remain available.

Validation: 22 calculation checks and three render checks covering all four
measures, default behavior, units, extrema labels, legend placement and early or
missing history. Next.js production build is required before deployment.
Signed-in browser interaction remains unverified without an authenticated
MULtipLY session. No new dependency, collection or data-definition change.
