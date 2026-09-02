# 8H-7B-2B — TradingView-Accessible Pine Parity Candidate Pool

Preserves the 2025 V1 candidate artifact and creates a separate 2026 V2 pool.

Accessible window: 2026-02-23 through 2026-08-28.

Run:
`python -m tests.test_pine_accessible_candidates`

Then:
`python -m tr_platform.parity.pine_accessible_candidates_cli`

Outputs:
- `docs/pmpd/parity/PMPD_V4_PINE_PARITY_CANDIDATES_V2.csv`
- `docs/pmpd/parity/PMPD_V4_PINE_PARITY_CANDIDATES_V2.json`

No Python PMPD signal output is used for selection.
