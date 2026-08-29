# 8H-6A-6H-2 — Multi-Symbol Historical-Engine Smoke Test

This gate proves the certified historical-data loader works across heterogeneous
production partitions, not just AAPL.

Sample:
- AAPL — SET_1
- SPY — SET_1 dense control
- JNJ — SET_2
- PANW — SET_3
- BKNG — SET_3 known source-sparse case
- ARM — SET_4

Each partition must:
- load through `load_certified_partition`
- remain RESEARCH_READY
- have valid manifest status
- verify SHA-256
- contain 250 trading dates for 2025
- expose usable PRE/RTH/AH session data

Run:

`python -m tests.test_multi_symbol_engine_smoke`

Then:

`python -m tr_platform.historical.multi_symbol_smoke_cli`

Both commands are read-only with respect to production cache/manifest.
