# Daily price chart
Thread: Tool: Sector Rotation Tracker
MWE: MWE-SECTOR-CANDLES-001 (E1, ZERO_INCREMENTAL_COST_FIRST)

A separate section below Sector Detail follows the exact session window and date
filters used by the heatmap. One daily candle per ETF session, chronological left
to right, with horizontal scrolling. Selection is shared with the heatmap and
detail chart. OHLC readout and keyboard selection are supported. The chart always
uses price, independent of heatmap return/rank measures. Color compares close to
open; it need not match close-to-close heatmap direction.

The existing Massive daily aggregate requests already include OHLC. Collectors
now validate and persist open/high/low together with close, preserving unchanged
price/rank definitions. Nullable additive columns retain historical append-only
observations; changed OHLC triggers a new version, and only COMPLETE collections
publish. Existing security-invoker views, RLS, allowlist and write grants remain.
The initial collection backfills available history. Missing OHLC stays blank.

Custom baskets show their existing closing index as a line with gaps. Member
highs and lows do not establish an actual basket intraday high/low; no synthetic
wicks are presented. IGV uses real ETF OHLC like the 11 sector ETFs. This does not
change basket membership, weights, return calculations or research datasets.

Verification: provider OHLC validity and missing-field rejection, candle date
window and gap checks, rendered section placement and date parity, basket gap
rendering, existing model tests and production Next.js build. Browser verification
requires an authenticated MULtipLY session and is not replaced by server rendering.
