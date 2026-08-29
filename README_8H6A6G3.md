# 8H-6A-6G-3 — Research Readiness Certification

This package formalizes the 2025 readiness gate using the validation artifacts
already produced by 6G-1, 6G-2, 6G-2A, and 6G-2B.

Policy:
- Structural integrity must pass for all 112 partitions.
- Coverage FAIL count must be zero.
- Coverage WARN rows are allowed only when they belong to the already-reviewed
  source-sparse symbols.
- Vendor-to-cache parity must pass for the forensic/control sample.
- Universe count must remain exactly 112/112.

The eight 2025 warning symbols are treated as known source-level sparsity:
MNDY, NOW, KLAC, BKNG, BLK, AXON, URI, REGN.

Run:
`python -m tr_platform.validation.readiness_certification_cli --year 2025`

A successful certification returns:
- Readiness status: RESEARCH_READY
- Research ready: True

This command is read-only with respect to the production cache and manifest.
It only writes a certification CSV in the validation directory.
