from __future__ import annotations

from dataclasses import dataclass, asdict
from getpass import getpass
from pathlib import Path
from typing import Callable, Iterable, Optional

import pandas as pd

from tr_platform.common.cache_config import CACHE_VERSION, SOURCE_NAME, MarketCacheConfig
from tr_platform.common.manifest import LocalManifest
from tr_platform.downloader.year_acquisition import (
    YearAcquisitionResult,
    _year_bounds,
    acquire_symbol_year,
)


@dataclass(frozen=True)
class BatchItemResult:
    symbol: str
    year: int
    action: str
    row_count: int
    success: bool
    error: Optional[str] = None


@dataclass(frozen=True)
class BatchRunSummary:
    total: int
    downloaded: int
    skipped_complete: int
    failed: int
    results: list[BatchItemResult]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def production_partition_is_complete(
    symbol: str,
    year: int,
    *,
    repo_root: Optional[Path] = None,
) -> bool:
    """
    Check whether the exact production MARKET_CACHE_V1 symbol/year partition
    is already complete without calling Massive or prompting for credentials.
    """
    symbol = symbol.upper().strip()

    if repo_root is None:
        repo_root = _repo_root()

    requested_start, requested_end = _year_bounds(year)

    cfg = MarketCacheConfig.from_repo_root(repo_root)
    output_path = cfg.symbol_year_path(symbol, year)
    manifest_path = cfg.manifests_root / "market_cache_manifest.parquet"
    manifest = LocalManifest(manifest_path)

    existing = manifest.get(
        symbol=symbol,
        year=year,
        timeframe="1m",
        source=SOURCE_NAME,
        adjusted=False,
        cache_version=CACHE_VERSION,
    )

    return (
        existing is not None
        and existing.get("download_status") == "DOWNLOADED"
        and existing.get("validation_status") in {"PASS", "PASS_WITH_WARNINGS"}
        and str(existing.get("requested_start")) == requested_start
        and str(existing.get("requested_end")) == requested_end
        and output_path.exists()
    )


def acquire_batch(
    items: Iterable[tuple[str, int]],
    *,
    api_key: Optional[str] = None,
    continue_on_error: bool = True,
    completeness_checker: Callable[[str, int], bool] = production_partition_is_complete,
    acquire_func: Callable[..., YearAcquisitionResult] = acquire_symbol_year,
    api_key_prompt: Callable[[str], str] = getpass,
) -> BatchRunSummary:
    """
    Hardened multi-partition acquisition.

    Improvements over 8H-6A-6D:
    - Does NOT request the Massive API key if every requested partition
      is already complete.
    - Prompts only when the first actual download is needed.
    - Continues after an individual partition failure when configured.
    - Preserves per-item results for audit/retry.
    """
    normalized_items = [(s.upper().strip(), int(y)) for s, y in items]
    shared_api_key = api_key

    results: list[BatchItemResult] = []

    for idx, (symbol, year) in enumerate(normalized_items, start=1):
        print()
        print(f"[{idx}/{len(normalized_items)}] {symbol} {year}")

        try:
            already_complete = completeness_checker(symbol, year)

            if already_complete:
                result = acquire_func(
                    symbol=symbol,
                    year=year,
                    api_key=None,
                )
            else:
                if shared_api_key is None:
                    shared_api_key = api_key_prompt(
                        "Enter your Massive API key for this batch: "
                    ).strip()

                result = acquire_func(
                    symbol=symbol,
                    year=year,
                    api_key=shared_api_key,
                )

            print(f"Action: {result.action}")
            print(f"Rows:   {result.row_count:,}")

            results.append(
                BatchItemResult(
                    symbol=symbol,
                    year=year,
                    action=result.action,
                    row_count=result.row_count,
                    success=True,
                )
            )

        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            print(f"FAILED: {message}")

            results.append(
                BatchItemResult(
                    symbol=symbol,
                    year=year,
                    action="FAILED",
                    row_count=0,
                    success=False,
                    error=message,
                )
            )

            if not continue_on_error:
                raise

    downloaded = sum(r.action == "DOWNLOADED" for r in results)
    skipped = sum(r.action == "SKIPPED_COMPLETE" for r in results)
    failed = sum(not r.success for r in results)

    return BatchRunSummary(
        total=len(results),
        downloaded=downloaded,
        skipped_complete=skipped,
        failed=failed,
        results=results,
    )


def print_batch_summary(summary: BatchRunSummary) -> None:
    print()
    print("=== BATCH ACQUISITION SUMMARY ===")
    print(f"Total:             {summary.total}")
    print(f"Downloaded:        {summary.downloaded}")
    print(f"Skipped complete:  {summary.skipped_complete}")
    print(f"Failed:            {summary.failed}")
    print()
    print("Per-item results:")

    rows = [asdict(r) for r in summary.results]
    df = pd.DataFrame(rows)
    if not df.empty:
        print(df.to_string(index=False))
