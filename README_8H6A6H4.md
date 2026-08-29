# 8H-6A-6H-4 — Failure / Guardrail Gate

This gate proves the certified historical loader fails closed.

Cases:
1. Unknown/non-universe symbol is rejected.
2. Non-certified year is rejected.
3. Missing production partition is rejected.
4. Valid Parquet with a manifest SHA-256 mismatch is rejected.
5. Dataset certification explicitly changed to NOT_READY is rejected.

The missing-file, hash-mismatch, and non-ready-certification tests operate only
on temporary isolated fixture copies. The production cache, manifest, and
certification files are not modified.

Run:
`python -m tests.test_historical_engine_guardrails`

Then:
`python -m tr_platform.historical.guardrail_gate_cli`

Passing result:
- Cases: 5
- PASS: 5
- FAIL: 0
- Production cache mutated: NO
