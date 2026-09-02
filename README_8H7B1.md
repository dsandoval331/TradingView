# 8H-7B-1 — Deterministic Reference-Sample Candidate Selection

This step creates the **candidate population**, not the final frozen 24-case
parity sample.

Why 48 candidates?
- Final parity target is 24 cases, 6 per frozen set.
- We need room to satisfy bullish/bearish, signal/no-signal, strong/weaker,
  favorable/adverse, early/late, and edge-case quotas using **Pine evidence**.
- Candidate selection must not use Python PMPD signal output.

Selection method:
- authoritative `PMPD_112_V1`
- certified 2025 trading dates
- frozen parity-protocol SHA-256 as deterministic seed
- one candidate date per selected symbol
- 12 distinct symbols per set
- required sparse-source coverage included
- no PMPD signal calculation is called

Run:

`python -m tests.test_reference_sample_candidates`

Then:

`python -m tr_platform.parity.reference_sample_candidates_cli`

Outputs:
- `docs/pmpd/parity/PMPD_V4_PARITY_SAMPLE_CANDIDATES_V1.csv`
- `docs/pmpd/parity/PMPD_V4_PARITY_SAMPLE_CANDIDATES_V1.json`
- deterministic manifest SHA-256

Next:
Use TradingView/Pine V4 evidence to classify these 48 candidates. Then freeze the
final 24-case sample according to the protocol quotas. Do not use Python PMPD
signal results during that classification.
