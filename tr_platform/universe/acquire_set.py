from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tr_platform.common.cache_config import CACHE_VERSION, SOURCE_NAME, MarketCacheConfig
from tr_platform.common.manifest import LocalManifest
from tr_platform.downloader.batch_acquisition import acquire_batch, print_batch_summary
from tr_platform.downloader.year_acquisition import _year_bounds
from tr_platform.universe.pmpd_universe import get_set_members


@dataclass(frozen=True)
class PartitionPlanItem:
    position_in_set: int
    symbol: str
    year: int
    status: str
    requested_start: str
    requested_end: str
    output_path: str


@dataclass(frozen=True)
class PartitionPlanSummary:
    set_number: int
    year: int
    total: int
    complete: int
    needs_download: int
    items: list[PartitionPlanItem]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_set_year_plan(
    *,
    set_number: int,
    year: int,
    repo_root_path: Optional[Path] = None,
) -> PartitionPlanSummary:
    if repo_root_path is None:
        repo_root_path = repo_root()

    members = get_set_members(repo_root_path, set_number)
    requested_start, requested_end = _year_bounds(year)

    cfg = MarketCacheConfig.from_repo_root(repo_root_path)
    cfg.ensure_directories()

    manifest_path = cfg.manifests_root / "market_cache_manifest.parquet"
    manifest = LocalManifest(manifest_path)

    items: list[PartitionPlanItem] = []

    for member in members:
        output_path = cfg.symbol_year_path(member.symbol, year)

        existing = manifest.get(
            symbol=member.symbol,
            year=year,
            timeframe="1m",
            source=SOURCE_NAME,
            adjusted=False,
            cache_version=CACHE_VERSION,
        )

        complete = (
            existing is not None
            and existing.get("download_status") == "DOWNLOADED"
            and existing.get("validation_status") in {"PASS", "PASS_WITH_WARNINGS"}
            and str(existing.get("requested_start")) == requested_start
            and str(existing.get("requested_end")) == requested_end
            and output_path.exists()
        )

        items.append(
            PartitionPlanItem(
                position_in_set=member.position_in_set,
                symbol=member.symbol,
                year=year,
                status="COMPLETE" if complete else "NEEDS_DOWNLOAD",
                requested_start=requested_start,
                requested_end=requested_end,
                output_path=str(output_path),
            )
        )

    complete_count = sum(i.status == "COMPLETE" for i in items)

    return PartitionPlanSummary(
        set_number=set_number,
        year=year,
        total=len(items),
        complete=complete_count,
        needs_download=len(items) - complete_count,
        items=items,
    )


def print_plan(summary: PartitionPlanSummary) -> None:
    print(f"=== PMPD SET_{summary.set_number} / {summary.year} ACQUISITION PLAN ===")
    print(f"Total partitions:   {summary.total}")
    print(f"Already complete:   {summary.complete}")
    print(f"Need download:      {summary.needs_download}")
    print()
    print("Partitions:")

    for item in summary.items:
        print(
            f"{item.position_in_set:>2}. "
            f"{item.symbol:<6} "
            f"{item.status:<14} "
            f"{item.requested_start} -> {item.requested_end}"
        )


def execute_set_year(
    *,
    set_number: int,
    year: int,
    confirm_execute: bool,
) -> None:
    summary = build_set_year_plan(set_number=set_number, year=year)
    print_plan(summary)

    if not confirm_execute:
        print()
        print("DRY RUN ONLY — no Massive API calls were made.")
        return

    if summary.needs_download == 0:
        print()
        print("All requested partitions are already complete. Nothing to download.")
        return

    items = [(item.symbol, year) for item in summary.items]

    print()
    print("=== EXECUTING BATCH ===")
    batch_summary = acquire_batch(items)
    print_batch_summary(batch_summary)

    if batch_summary.failed:
        raise SystemExit(1)
