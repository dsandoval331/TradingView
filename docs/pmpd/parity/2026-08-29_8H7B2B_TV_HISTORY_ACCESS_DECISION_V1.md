# PM + Previous Day Breakout
## 8H-7B-2B — TradingView History Accessibility Decision V1

**Decision code:** `PMPD_8H7B2B_TV_HISTORY_ACCESS_V1`
**Date:** 2026-08-29
**Status:** DRAFT_FOR_FREEZE

TradingView 5-minute history was empirically accessible only back to 2026-02-23.
Therefore the frozen 2025 candidate manifest is preserved unchanged, but it is
not used as genuine Pine-observed parity evidence.

A separate Pine-observed candidate pool will use only dates from
2026-02-23 through 2026-08-28. Selection remains deterministic and does not use
Python PMPD signal output. Pine classifies the candidate pool first; the final
24-case sample is frozen before Python parity comparison.
