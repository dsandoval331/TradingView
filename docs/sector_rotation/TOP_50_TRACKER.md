# S&P 500 Top 50 Index constituent tracker

Replaces Frequently Traded. Canonical route `/dashboard/sector-rotation/stocks/top-50`; old `/stocks/frequent` redirects. Home and all tracker navigation use the new name and URL.

`stocks/top50.json` freezes common-stock holdings from Invesco XLG as of 2026-10-23 (issuer file dated 2026-10-24), including source URL and SHA-256. 51 securities represent 50 companies because Alphabet has two classes. BRK/B maps to provider symbol BRK.B. Excludes money market, currency and lending positions. This is a dated ETF membership proxy, not licensed index levels or a point-in-time reconstruction. Membership changes require a reviewed snapshot update; not automatically reconstituted.

The existing stock archive collector seeds members idempotently and collects SPY, all index constituents, then lookup requests, bounded at 80 symbols. Existing schedule, provider and credentials remain. Workflow timeout is 40 minutes to allow paced requests. No synthetic prices or invented weighted index return. All existing daily candles, EMA selector/20E, directional averages, ranking and linked scrolling remain.

MWE-SECTOR-STOCKS-001 remains the authorized stock collection lane. This change adds the requested index universe; research datasets and access policies are unchanged.
