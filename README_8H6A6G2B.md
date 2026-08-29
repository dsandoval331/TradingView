# 8H-6A-6G-2B — Vendor vs Cache Ground-Truth Parity

Uses the repository's existing `MassiveClient` and
`normalize_massive_minute_rows`; no parallel API implementation.

Live cases:
- BKNG 2025-07-24 — primary 80-minute-gap forensic case
- NOW 2025-06-09 — warning-symbol comparison
- MNDY 2025-07-24 — warning-symbol comparison
- SPY 2025-07-24 — dense control

The command prompts once for the Massive API key and performs read-only API
queries. It does not alter cached partitions or the manifest.

It compares RTH timestamp sets and OHLCV values between a fresh vendor response
and the existing canonical cache.

Run:
`python -m tr_platform.validation.vendor_cache_parity_cli`
