# 8H-6A-6G-2A — Coverage Warning Forensics

This diagnostic follows the 2025 coverage audit:

- PASS: 104
- WARN: 8
- FAIL: 0

Warning symbols:
MNDY, NOW, KLAC, BKNG, BLK, AXON, URI, REGN.

The goal is **not** to redownload or mutate data. It characterizes the warnings
before we decide whether they represent valid low-activity minutes, edge-session
effects, halts, or suspicious internal data gaps.

For every RTH day it records:
- RTH bar count
- first and last RTH timestamps
- largest within-day gap
- number of >5m and >15m gaps
- exact start/end of the largest gap
- missing minutes at the opening/closing edges

It also creates an 8-symbol summary with median/minute-density statistics and
the exact worst gap for each symbol, including a dedicated BKNG focus.

Run from repo root:

```powershell
python -m tr_platform.validation.warning_forensics_cli --year 2025
```

This is read-only. Do not set `research_ready=true` until the warning patterns
have been reviewed.
