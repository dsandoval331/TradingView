from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import pandas as pd

from tr_platform.historical.certified_dataset import load_certified_partition


DEFAULT_SAMPLE = [
    # SET_1
    ("AAPL", 2025),
    ("SPY", 2025),
    # SET_2
    ("JNJ", 2025),
    # SET_3
    ("PANW", 2025),
    ("BKNG", 2025),  # known source-sparse symbol
    # SET_4
    ("ARM", 2025),
]


@dataclass(frozen=True)
class SymbolSmokeResult:
    symbol: str
    year: int
    rows: int
    rth_rows: int
    pre_rows: int
    ah_rows: int
    trading_days: int
    first_et: str
    last_et: str
    certification_status: str
    manifest_validation_status: str
    sha256_length: int
    status: str


@dataclass(frozen=True)
class MultiSymbolSmokeSummary:
    total: int
    passed: int
    failed: int
    results: list[SymbolSmokeResult]


def run_multi_symbol_smoke(
    *,
    sample: list[tuple[str, int]] = DEFAULT_SAMPLE,
    repo_root: Optional[Path] = None,
    verify_hash: bool = True,
) -> MultiSymbolSmokeSummary:
    results: list[SymbolSmokeResult] = []
    failures = 0

    for symbol, year in sample:
        try:
            p = load_certified_partition(
                symbol=symbol,
                year=year,
                repo_root=repo_root,
                verify_hash=verify_hash,
            )

            df = p.dataframe
            session_counts = df["session"].value_counts()
            trading_days = int(pd.to_datetime(df["trade_date"]).nunique())

            result = SymbolSmokeResult(
                symbol=symbol,
                year=year,
                rows=len(df),
                rth_rows=int(session_counts.get("RTH", 0)),
                pre_rows=int(session_counts.get("PRE", 0)),
                ah_rows=int(session_counts.get("AH", 0)),
                trading_days=trading_days,
                first_et=str(pd.to_datetime(df["timestamp_et"]).min()),
                last_et=str(pd.to_datetime(df["timestamp_et"]).max()),
                certification_status=p.certification_status,
                manifest_validation_status=p.manifest_validation_status,
                sha256_length=len(p.file_sha256),
                status="PASS",
            )
        except Exception as exc:
            failures += 1
            result = SymbolSmokeResult(
                symbol=symbol,
                year=year,
                rows=0,
                rth_rows=0,
                pre_rows=0,
                ah_rows=0,
                trading_days=0,
                first_et="",
                last_et="",
                certification_status="",
                manifest_validation_status="",
                sha256_length=0,
                status=f"FAIL: {type(exc).__name__}: {exc}",
            )

        results.append(result)

    return MultiSymbolSmokeSummary(
        total=len(results),
        passed=len(results) - failures,
        failed=failures,
        results=results,
    )


def write_smoke_report(
    summary: MultiSymbolSmokeSummary,
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

    out_path = out_dir / "PMPD_112_V1_2025_multi_symbol_engine_smoke.csv"
    pd.DataFrame([asdict(r) for r in summary.results]).to_csv(out_path, index=False)
    return out_path
