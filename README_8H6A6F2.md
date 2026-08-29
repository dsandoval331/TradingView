# 8H-6A-6F-2 — Universe → Acquisition Integration

This package connects the authoritative frozen PMPD universe loader to the
hardened production acquisition engine.

## Safety design

The CLI is **dry-run by default**.

This command:

```powershell
python -m tr_platform.universe.acquire_set_cli --set 1 --year 2025
```

prints the acquisition plan and makes **no Massive API calls**.

Actual acquisition requires the explicit flag:

```powershell
python -m tr_platform.universe.acquire_set_cli --set 1 --year 2025 --execute
```

## Files

- `tr_platform/universe/acquire_set.py`
- `tr_platform/universe/acquire_set_cli.py`
- `tests/test_universe_acquisition_plan.py`

## First test

```powershell
python -m tests.test_universe_acquisition_plan
```

Expected:
- 28 total Set 1 partitions
- AAPL/MSFT/NVDA 2025 already COMPLETE
- Remaining partitions marked NEEDS_DOWNLOAD

## Then run dry-run

```powershell
python -m tr_platform.universe.acquire_set_cli --set 1 --year 2025
```

Do **not** add `--execute` until the dry-run output is reviewed.
