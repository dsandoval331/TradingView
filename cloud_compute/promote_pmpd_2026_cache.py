from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from cloud_compute.manifest import sha256_file
from cloud_compute.storage_poc import DEFAULT_BUCKET, _download_object, _upload_object

DEFAULT_CACHE_ROOT = Path("data/second1m_alt_entry_cache_v1/partitions")
DEFAULT_CONTEXT = Path("research_outputs/pmpd/post9n_batch1/context_enriched.parquet")
DEFAULT_PREFIX = "upstream/pmpd/market_cache/1m"
DEFAULT_OUTPUT = Path("research_outputs/cloud_compute/pmpd_edge_e1_b5_2026_cache_promotion.json")


def _required_symbols(context_path: Path) -> list[str]:
    if not context_path.is_file():
        raise FileNotFoundError(f"context artifact not found: {context_path}")
    df = pd.read_parquet(context_path, columns=["symbol"])
    return sorted(df["symbol"].astype(str).str.upper().dropna().unique().tolist())


def promote_symbol(
    symbol: str,
    *,
    cache_root: Path,
    project_url: str,
    secret_key: str,
    bucket: str,
    object_prefix: str,
) -> dict:
    source = (cache_root / symbol / f"{symbol}_2026.parquet").resolve()
    if not source.is_file():
        raise FileNotFoundError(f"required 2026 partition missing: {source}")

    object_path = f"{object_prefix.rstrip('/')}/{symbol}/2026.parquet"
    size = source.stat().st_size
    digest = sha256_file(source)
    upload_status = _upload_object(
        project_url,
        secret_key,
        bucket,
        object_path,
        source,
        allow_existing=True,
    )

    with tempfile.TemporaryDirectory(prefix=f"tr-pmpd-b5-{symbol.lower()}-") as tmpdir:
        downloaded = Path(tmpdir) / f"{symbol}_2026.parquet"
        _download_object(project_url, secret_key, bucket, object_path, downloaded)
        remote_size = downloaded.stat().st_size
        remote_sha = sha256_file(downloaded)

    if remote_size != size or remote_sha != digest:
        raise RuntimeError(
            f"remote parity failed for {symbol}: local={size}/{digest} remote={remote_size}/{remote_sha}"
        )

    return {
        "symbol": symbol,
        "year": 2026,
        "bucket_name": bucket,
        "object_path": object_path,
        "local_relative_path": f"data/second1m_alt_entry_cache_v1/partitions/{symbol}/{symbol}_2026.parquet",
        "size_bytes": size,
        "sha256": digest,
        "upload_status": upload_status,
        "parity": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Promote every 2026 PMPD universe 1-minute partition required by PMPD-EDGE E1 Batch 5 "
            "to private Supabase Storage and verify exact size/SHA-256 parity."
        )
    )
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--context", type=Path, default=DEFAULT_CONTEXT)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--object-prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")

    symbols = _required_symbols(args.context)
    if not symbols:
        raise RuntimeError("no required symbols found in context artifact")

    missing = [
        symbol
        for symbol in symbols
        if not (args.cache_root / symbol / f"{symbol}_2026.parquet").is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "missing required canonical 2026 partitions before promotion: " + ", ".join(missing)
        )

    rows = []
    for idx, symbol in enumerate(symbols, 1):
        print(f"[{idx}/{len(symbols)}] PROMOTE {symbol} 2026")
        rows.append(
            promote_symbol(
                symbol,
                cache_root=args.cache_root,
                project_url=url,
                secret_key=key,
                bucket=args.bucket,
                object_prefix=args.object_prefix,
            )
        )

    record = {
        "manifest_version": 1,
        "purpose": "PMPD-EDGE-E1-B5 governed canonical 2026 raw 1-minute dependencies",
        "promoted_at_utc": datetime.now(timezone.utc).isoformat(),
        "context_path": str(args.context),
        "required_symbol_count": len(symbols),
        "promoted_symbol_count": len(rows),
        "all_parity_pass": all(bool(r["parity"]) for r in rows),
        "entries": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("PMPD_EDGE_E1_B5_2026_CACHE_PROMOTION=PASS")
    print(f"SYMBOLS={len(rows)}")
    print(f"OUTPUT={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
