from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
from typing import Optional
import json

import pandas as pd

from tr_platform.historical.certified_dataset import load_certified_partition


DEFAULT_SAMPLE = [
    ("AAPL", 2025),
    ("SPY", 2025),
    ("JNJ", 2025),
    ("PANW", 2025),
    ("BKNG", 2025),
    ("ARM", 2025),
]


@dataclass(frozen=True)
class PartitionFingerprint:
    symbol: str
    year: int
    row_count: int
    first_timestamp_utc: str
    last_timestamp_utc: str
    file_sha256: str
    rth_rows: int
    pre_rows: int
    ah_rows: int
    trading_days: int
    close_sum: float
    volume_sum: float
    fingerprint_sha256: str


@dataclass(frozen=True)
class DeterminismRun:
    run_number: int
    partition_fingerprints: list[PartitionFingerprint]
    aggregate_fingerprint_sha256: str


def _stable_float(value: float) -> float:
    return float(f"{float(value):.10f}")


def _partition_fingerprint(symbol: str, year: int, repo_root: Optional[Path]) -> PartitionFingerprint:
    p = load_certified_partition(
        symbol=symbol,
        year=year,
        repo_root=repo_root,
        verify_hash=True,
    )
    df = p.dataframe
    counts = df["session"].value_counts()

    payload = {
        "symbol": symbol,
        "year": year,
        "row_count": len(df),
        "first_timestamp_utc": str(pd.to_datetime(df["timestamp_utc"]).min()),
        "last_timestamp_utc": str(pd.to_datetime(df["timestamp_utc"]).max()),
        "file_sha256": p.file_sha256,
        "rth_rows": int(counts.get("RTH", 0)),
        "pre_rows": int(counts.get("PRE", 0)),
        "ah_rows": int(counts.get("AH", 0)),
        "trading_days": int(pd.to_datetime(df["trade_date"]).nunique()),
        "close_sum": _stable_float(df["close"].sum()),
        "volume_sum": _stable_float(df["volume"].sum()),
    }

    fp = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return PartitionFingerprint(
        fingerprint_sha256=fp,
        **payload,
    )


def run_determinism_pass(
    *,
    run_number: int,
    sample: list[tuple[str, int]] = DEFAULT_SAMPLE,
    repo_root: Optional[Path] = None,
) -> DeterminismRun:
    parts = [
        _partition_fingerprint(symbol, year, repo_root)
        for symbol, year in sample
    ]

    aggregate_payload = [
        asdict(p) for p in parts
    ]
    agg = sha256(
        json.dumps(
            aggregate_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return DeterminismRun(
        run_number=run_number,
        partition_fingerprints=parts,
        aggregate_fingerprint_sha256=agg,
    )


def compare_runs(a: DeterminismRun, b: DeterminismRun) -> list[str]:
    issues: list[str] = []

    if a.aggregate_fingerprint_sha256 != b.aggregate_fingerprint_sha256:
        issues.append(
            "aggregate_fingerprint_mismatch:"
            f"{a.aggregate_fingerprint_sha256}!={b.aggregate_fingerprint_sha256}"
        )

    amap = {p.symbol: p for p in a.partition_fingerprints}
    bmap = {p.symbol: p for p in b.partition_fingerprints}

    if set(amap) != set(bmap):
        issues.append("symbol_set_mismatch")

    for symbol in sorted(set(amap) & set(bmap)):
        if asdict(amap[symbol]) != asdict(bmap[symbol]):
            issues.append(f"partition_mismatch:{symbol}")

    return issues


def write_determinism_report(
    run_a: DeterminismRun,
    run_b: DeterminismRun,
    issues: list[str],
    *,
    repo_root: Optional[Path] = None,
) -> Path:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]

    out_dir = (
        repo_root
        / "market_cache"
        / "MARKET_CACHE_V1"
        / "validation"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "PMPD_112_V1_2025_determinism_report.csv"

    rows = []
    for run in [run_a, run_b]:
        for p in run.partition_fingerprints:
            row = asdict(p)
            row["run_number"] = run.run_number
            row["aggregate_fingerprint_sha256"] = run.aggregate_fingerprint_sha256
            row["comparison_status"] = "PASS" if not issues else "FAIL"
            row["issues"] = "; ".join(issues)
            rows.append(row)

    pd.DataFrame(rows).to_csv(out_path, index=False)
    return out_path
