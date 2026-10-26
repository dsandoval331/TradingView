# Stock Lookup and Frequently Traded
Thread: Tool: Sector Rotation Tracker
MWE: MWE-SECTOR-STOCKS-001 | E1 | ZERO_INCREMENTAL_COST_FIRST

New routes /dashboard/sector-rotation/stocks and /stocks/frequent, linked beside
Tech & AI detail on every tracker page. Stock Lookup accepts normalized ticker
text (optional $ prefix). Its allowlisted server action inserts only a symbol
request, not prices or secrets. Already archived symbols display immediately;
new symbols await the next overnight collection. Form and query input are
validated. Capacity is bounded to 30 symbols including SPY. The fixed frequent
list is MSFT, AAPL, NVDA, TSLA, AMD, in that order.

Both pages reuse historical heatmap, latest price/percent, EMA toggle and 20E
markers, directional averages, completed streaks, multi-session returns, CSV,
performance chart, daily candles and linked scrolling. Single-stock ranks and
leadership are omitted; frequent-stock ranks compare only those five stocks.
Individual stocks have no ETF holdings table. Existing sector semantics remain.

Isolated stock_tracker_symbols, stock_tracker_runs, stock_daily_observations and
security-invoker v_stock_daily_latest. RLS uses the existing MULtipLY allowlist.
Authenticated roles can read and request symbol names; cannot write prices,
collection status, success times or error metadata. Anonymous access is revoked.
Each symbol has its own append-only collection run and response hash. Only
COMPLETE runs publish. Failed symbols retain previous prices and report an error.
SPY is the session calendar; shorter listed histories are allowed, foreign dates
or stale final sessions are rejected. Missing sessions are never bridged.

Collector scripts/stock_tracker/collect.py reuses existing Massive request and
OHLC normalization helpers. At most 30 symbols/run, 15s between requests,
bounded retries and 25-minute job timeout. Shared provider concurrency retained.
Workflow .github/workflows/sector-stocks-daily.yml runs on relevant main pushes
and at 08:15/12:15 UTC Tuesday–Saturday, plus manual dispatch.
No new paid service; actual incremental dollars not certified. Available
729-day provider window rechecked for changes, split-adjusted without dividends.
Secrets stay in existing GitHub Actions environment.

Validation: 45 Node model/render checks, 12 Python collector checks, production
Next.js build/typecheck; RLS/grants/view checks and security advisor (no stock
findings). First backfill and coverage require remote readback. Authenticated
browser/form end-to-end testing requires a valid user session and is not inferred
from build or SQL success.
