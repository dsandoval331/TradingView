from __future__ import annotations

import argparse
import getpass
import hashlib
from pathlib import Path

import pandas as pd
import requests

COLUMNS = ["symbol", "trade_date", "open", "high", "low", "close", "volume"]
DEFAULT_OBJECT = "governed_inputs/swing10/s2_b1/market_daily_history_2025-02-03_2026-08-27.csv"


def main() -> int:
    p = argparse.ArgumentParser(description="Export the canonical SW10 daily panel as an immutable governed input")
    p.add_argument("--supabase-url", default="https://vrdesbkgxssupfqnrrag.supabase.co")
    p.add_argument("--bucket", default="trading-research-market-data")
    p.add_argument("--object-path", default=DEFAULT_OBJECT)
    p.add_argument("--out", default="research_outputs/swing10/s1/market_daily_history_2025-02-03_2026-08-27.csv")
    a = p.parse_args()

    key = getpass.getpass("Supabase secret key (not stored): ").strip()
    if not key:
        raise SystemExit("Supabase secret key is required")
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    endpoint = f"{a.supabase_url.rstrip('/')}/rest/v1/market_daily_history"
    rows = []
    offset = 0
    while True:
        r = requests.get(endpoint, headers=headers, params={"select": ",".join(COLUMNS), "order": "symbol.asc,trade_date.asc", "limit": 1000, "offset": offset}, timeout=60)
        r.raise_for_status()
        page = r.json()
        if not isinstance(page, list):
            raise RuntimeError("unexpected REST response")
        rows.extend(page)
        if len(page) < 1000:
            break
        offset += len(page)

    frame = pd.DataFrame(rows, columns=COLUMNS).sort_values(["symbol", "trade_date"], kind="stable").reset_index(drop=True)
    if frame.empty:
        raise RuntimeError("canonical daily panel export is empty")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False, lineterminator="\n")
    data = out.read_bytes()
    digest = hashlib.sha256(data).hexdigest()

    upload = f"{a.supabase_url.rstrip('/')}/storage/v1/object/{a.bucket}/{a.object_path}"
    u = requests.post(upload, headers={**headers, "Content-Type": "text/csv", "x-upsert": "false"}, data=data, timeout=120)
    if u.status_code not in (200, 201):
        raise RuntimeError(f"storage upload failed {u.status_code}: {u.text[:500]}")

    print(f"ROWS={len(frame)}")
    print(f"SYMBOLS={frame['symbol'].nunique()}")
    print(f"MIN_DATE={frame['trade_date'].min()}")
    print(f"MAX_DATE={frame['trade_date'].max()}")
    print(f"SIZE_BYTES={len(data)}")
    print(f"SHA256={digest}")
    print(f"BUCKET={a.bucket}")
    print(f"OBJECT_PATH={a.object_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
