# 8H-6A-6G-2 — 2025 Coverage Quality Audit

This is the second dataset-readiness gate after the 112/112 structural-integrity
audit passed.

It measures, per symbol:
- total trading dates represented
- RTH / PRE / AH day counts
- RTH / PRE / AH row counts
- sparse RTH days (<300 and <350 one-minute bars)
- well-populated RTH days (>=380 bars)
- largest within-day RTH timestamp gap
- count of days with >5-minute and >15-minute RTH gaps
- first and last represented trade dates

The thresholds are intentionally tolerant. This step is meant to identify
partitions needing review, not silently delete or repair data.

Run from repository root:

```powershell
python -m tr_platform.validation.coverage_quality_cli --year 2025
```

Do not set research_ready=true solely because this command completes. Review any
WARN/FAIL rows first. A clean 112 PASS / 0 WARN / 0 FAIL is the ideal outcome.
