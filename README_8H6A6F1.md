# 8H-6A-6F-1 — Frozen Universe Batch Loader

This package intentionally does **not** create a second independent 112-symbol list.

The loader parses the existing authoritative migration:

`sql/migrations/2026-08-28_Migration_004_PMPD_112_Universe_Registration.sql`

That migration remains the local version-controlled source for `PMPD_112_V1`.

## Files

- `tr_platform/universe/pmpd_universe.py`
- `tr_platform/universe/preflight.py`
- `tests/test_pmpd_universe_loader.py`

## Step 1 — loader validation

From repo root:

```powershell
python -m tests.test_pmpd_universe_loader
```

Expected:

```text
=== PMPD_112_V1 LOADER TEST PASS ===
Total members: 112
Unique symbols: 112
SET_1/2/3/4: 28 each
SET_1 #12: CVX
SET_4 #27: CVS
Set 1 first/last: MSFT / TQQQ
Set 4 first/last: ARM / NEE
```

## Step 2 — Set 1 / 2025 preflight

```powershell
python -m tr_platform.universe.preflight --set 1 --year 2025
```

This is read-only. It performs no API call and no acquisition.

It should print exactly 28 Set 1 partitions in authoritative order.
