# MULtipLY — directional daily-move context

Thread: Tool: Sector Rotation Tracker
MWE: MWE-SECTOR-NORMAL-001
Authority: E1 | ZERO_INCREMENTAL_COST_FIRST

The selected ETF/group detail now shows average up-day and down-day moves,
matching sample counts, and whether the selected move is larger/smaller than
its same-direction average. Both main-sector and Tech & AI views use this panel.

## Definition

- Measure: daily split-adjusted close-to-close PRICE return, in percent. This
  includes overnight price changes, excludes dividends, and is not an intraday
  high/low range, ATR, or return relative to SPY.
- Baseline: the 60 SPY-reference sessions strictly BEFORE the selected session.
  The selected session, future sessions and older observations are excluded.
- Average up day: arithmetic mean of positive daily returns in that window.
- Average down day: arithmetic mean of negative returns, displayed signed.
- Flat: absolute return <= 1e-10 percentage points (roundoff tolerance). Flats
  are counted separately and excluded from directional means.
- Comparison: absolute selected return / absolute matching-direction mean.
  Percent difference in size = 100 × (ratio − 1).
  Example: a −2% move versus a −1% average down day is 2× size, 100% larger.
- Means and counts are shown for available observations. The comparison itself
  requires 60 valid prior daily returns and at least five matching-direction
  observations. Partial history, missing observations, absent directional
  samples, flat selected sessions and unavailable selected returns are labeled;
  no ratio is fabricated. Missing values are not filled and do not extend the
  calendar window backward.
- The baseline uses FULL loaded history, independently of visible heatmap
  filters. Selecting a historical date recalculates its earlier-only baseline.
- Custom baskets use their existing computed daily price-index returns, with
  all previously disclosed membership and rebalancing limitations.

This is a descriptive statistic, not a probability forecast, calibrated
outlier threshold, trading signal, or change to any frozen research methodology.
Existing return/rank calculations, constituents, CSV output and collectors are
unchanged. No external data service or paid dependency is added.

## Verification

Twenty model checks pass: 12 existing checks and 8 directional-statistic checks
covering window boundaries, selected/future exclusion, positive/negative
magnitudes, flat/missing/nonfinite values, partial windows and minimum samples.
The Next.js production build passes.

A live XLK comparison through 2026-10-23 matched an independent PostgreSQL
calculation: prior 60 sessions contained 30 up, 29 down and 1 flat session;
average up +1.3260359803%, average down −1.0328860567%, selected +0.4880991554%.
The selected up move was 0.3680889227× its up-day mean, 63.1911077333% smaller.
No selected/future return enters those averages.

Signed-in browser interaction QA remains unverified without an authenticated
MULtipLY session; no authentication bypass is introduced.
